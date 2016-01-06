# Create your views here.
#from reportlab.pdfgen import canvas
#from django.http import HttpResponse

from datetime import date
from django.shortcuts import render_to_response, render, redirect
from django.template.context import RequestContext
from django.http import HttpResponseRedirect
from django.db.models import Sum
#from django.contrib.gis.geoip import GeoIP
from django.conf import settings

from accounts.models import Expense, Donation, DonationFund, PAYMENT_GATEWAY, \
    DIRECT
from people.models import Person

from accounts.forms import PaymentTempForm, PledgeForm
from accounts.models import PaymentTemp, Pledge
from accounts.util import get_post_object
from accounts.forms import CCAVenueReturnForm
from django.views.decorators.csrf import csrf_exempt
import math
from django.contrib.auth.models import User
from ext.notification import models as notification_models
from utils.models import LakshyaTestimonial

def expenses_home(request):
    expenses_list = Expense.objects.all()
    context = {"expenses_list" : expenses_list}
    return render_to_response("expenses.html",
                              RequestContext(request, context))

def donations_home(request):
    donor_details_list = [] #list of tuples - name, batch, branch, amount, last Donated on
    top_donor_details_list = [] #list of top donors
    freq_donor_details_list = [] #list of most frequent donors
    for temp_dict in Donation.objects.values('donor').annotate(total=Sum('amount')):
        donor_id = temp_dict["donor"]
        total = temp_dict["total"]
        donor = Person.objects.get(id=donor_id)
	count = Donation.objects.filter(donor=donor).count() ## top frequent donors
        last_donated_on = Donation.objects.filter(donor=donor).order_by("-date_of_donation")[0].date_of_donation
        donor_details = (donor.name, donor.year_of_passing, donor.get_department_display, total, last_donated_on)
	freq_donor_details = (donor.name, count, total)
	top_donor_details = (donor.name, total)
        donor_details_list.append(donor_details)
	if not donor_id in [26, 27]: # Excluding Anonymous and Bank Interest from these lists
		top_donor_details_list.append(top_donor_details) ##
		freq_donor_details_list.append(freq_donor_details) ##

    total_donation_amount = Donation.objects.all().aggregate(Sum("amount"))["amount__sum"]
    donor_distinct_set = set()
    for donation in Donation.objects.all():
        donor_distinct_set.add(donation.donor.id)
    total_donors = len(donor_distinct_set)

    avg_donation_amount = total_donation_amount / total_donors

    top_donor_details_list = sorted(top_donor_details_list, key=lambda donors: donors[1], reverse=True) ##
    del top_donor_details_list[4:] ##

    freq_donor_details_list = sorted(freq_donor_details_list, key=lambda donors: donors[1], reverse=True) ##
    del freq_donor_details_list[4:] ##

    context = {"donor_details_list" : donor_details_list,
               "total_donation_amount" : total_donation_amount,
               "total_donors" : total_donors,
               "avg_donation_amount" : avg_donation_amount,
	       "top_donor_details_list" : top_donor_details_list,
	       "freq_donor_details_list" : freq_donor_details_list}
    return render_to_response("donations.html",
                              RequestContext(request, context))

def donate_home(request):
    form = PaymentTempForm()
    form.fields['referrer_url'].initial = request.get_full_path()
    if '/applicants' in request.get_full_path():
	return render(request, 'research_facilitator_applicants.html', {
        'form': form
    	})
    elif '/donate' in request.get_full_path():
        testimonial_list = LakshyaTestimonial.objects.order_by('?')[:2]
	return render(request, 'donate.html', {
        'form': form, 'testimonial_list': testimonial_list
    	})

def payment_redirect(request):
    referrer_url = ""
    notes = ""
    if request.method == 'POST': # If the form has been submitted...
        form = PaymentTempForm(request.POST) # A form bound to the POST data
        referrer_url = form.data['referrer_url']
        notes = form.data['flex_field']
        if form.is_valid(): # All validation rules passes
            # Process the data in form.cleaned_data
            amount = form.cleaned_data['amount']
            email_address = form.cleaned_data['email_address']
            email_receipt = form.cleaned_data['email_receipt']
            pan_card = form.cleaned_data['pan_card']
	    if referrer_url == '/applicants' and notes <> "":
	    	notes = "Internship Sponroship for " + notes
            print "Creating PaymentTemp"
            pt = PaymentTemp.objects.create(amount=amount, email_address=email_address, email_receipt=email_receipt, pan_card=pan_card)
            transaction_id = pt.id
            if settings.ENV == "stage":
                transaction_id = "stage" + str(pt.id)
            callback_url = "http://www.thelakshyafoundation.org/accounts/payment-return"
            context = {"payment_dict" : get_post_object(callback_url, amount, email_address, transaction_id, notes)}
            return render_to_response("payment_redirect.html",
                              RequestContext(request, context))
    else:
        form = PaymentTempForm() # An unbound form
    if referrer_url == '/applicants':
	return render(request, 'research_facilitator_applicants.html', {
	'form': form,
	})
    elif referrer_url == '/donate' or 'pledge' in referrer_url:
	return render(request, 'donate.html', {
	'form': form,
	})


@csrf_exempt
def return_view(request):
#    import pdb; pdb.set_trace()
    if request.method == "POST":
        working_key = "vsb2w5ampye1baft0hg62jlwrscw007u"
        merchant_id = "M_thelaksh_10884"

        form = CCAVenueReturnForm(merchant_id, working_key, request.POST)
        if not form.is_valid():
            return redirect("payment-failure")


        if form.cleaned_data['AuthDesc'] == 'N':
            return redirect("payment-failure")

        try:
            temp_id = request.POST.get("Order_Id")
            if settings.ENV == "dev":
                #order_id will be like dev11
                temp_id = int(request.POST.get("Order_Id").split("dev")[1])
            paymentTemp = PaymentTemp.objects.get(id=temp_id)
        except PaymentTemp.DoesNotExist:
            print "Error: Shouldn't have come here.PaymentTemp is missing"
            return redirect("payment-success")

        try:
            user = User.objects.get(email=paymentTemp.email_address)
        except User.DoesNotExist:
            user = User.objects.create(username=paymentTemp.email_address[:28],
                                       email=paymentTemp.email_address,
                                       first_name=request.POST.get("billing_cust_name"),
                                       password="Lakshya123$")
        try:
            person = Person.objects.get(user=user)
            person.billing_address = str(request.POST.get("billing_cust_address"))
            person.billing_city = str(request.POST.get("billing_cust_city"))
            person.billing_state = str(request.POST.get("billing_cust_state"))
            person.billing_postal_code = str(request.POST.get("billing_zip_code"))
            person.billing_country = str(request.POST.get("billing_cust_country"))
            person.contact_number = str(request.POST.get("billing_cust_tel"))
            person.save()
        except Person.DoesNotExist:
            person = Person.objects.create(user=user,
                                           billing_address=str(request.POST.get("billing_cust_address")),
                                           billing_city=str(request.POST.get("billing_cust_city")),
                                           billing_state=str(request.POST.get("billing_cust_state")),
                                           billing_postal_code=str(request.POST.get("billing_zip_code")),
                                           billing_country=str(request.POST.get("billing_cust_country")),
                                           contact_number=str(request.POST.get("billing_cust_tel")),
                                           )
        if paymentTemp.pan_card:
            person.pan_number = paymentTemp.pan_card
            person.save()

        Donation.objects.create(amount=request.POST.get("Amount"),
                                date_of_donation=date.today(),
                                donor=person,
                                donation_fund=DonationFund.objects.filter(name__contains="Lakshya")[0],
                                transacation_type=PAYMENT_GATEWAY,
                                transaction_details="CCAvenue Id: " + str(request.POST.get("Order_Id")) + " " + paymentTemp.flex_field,
                                donation_type=DIRECT,
                                is_repayment=False,)

        info_user = User(first_name="Lakshya", last_name="Foundation",
                       email="info@thelakshyafoundation.org", id=1)

        to_users = [user, info_user]

        context = {"name": request.POST.get("billing_cust_name"),
                   "amount": request.POST.get("Amount")}

        notification_models.send(to_users, "payment_confirmation", context)

        return redirect("payment-success")
    else:
        return redirect("payment-failure")


def calc_amount(ip):
    """
    Calculate amount - Determine if it is $500 or Rs 10000
    """
    g = GeoIP(path=settings.PROJECT_DIR + "/libraries/geoip")
    country = g.country(ip)
    if country["country_code"] and country["country_code"] in ["AU", "AT", "JP", "US", "CA", "GB", "CH", "SE", \
                                                                "ES", "SG", "DK", "JP", "IT", "DE" ]:
        return True
    return False

def seedfund(request):
    ip = request.META.get('HTTP_X_REAL_IP')
    if settings.ENV and settings.ENV == "dev":
        ip = "127.0.0.1"
    is_dollar = calc_amount(ip)
    show_success_message = False
    if request.method == "POST":
        form = PledgeForm(request.POST)
        if not form.is_valid():
            pass
        else:
            if not Pledge.objects.filter(email=form.cleaned_data['email']):
                rs_or_dollar = 500 if is_dollar else 10000
                donation_amount = 25000 if is_dollar else 10000
                pledge = Pledge(name=form.cleaned_data['name'], email=form.cleaned_data['email'], batch=form.cleaned_data['batch'],
                            rs_or_dollar=rs_or_dollar, month_of_donation=form.cleaned_data['month_of_donation'], donation_amount=donation_amount)
                pledge.save()
            show_success_message = True
            form = PledgeForm()
    else:
        form = PledgeForm()
    donations = Pledge.objects.filter(has_donated=True)
    pledges = Pledge.objects.filter(has_donated=False)
    pledge_percentage = Pledge.objects.all().aggregate(Sum("donation_amount"))['donation_amount__sum'] * 100 / 1500000
    pledge_percentage = str(math.ceil(pledge_percentage * 100) / 100) + " %"
    return render_to_response("seed_fundraising.html",
                              RequestContext(request, {'form' : form, "donations" : donations, "pledges":pledges,
                                                       "pledge_percentage":pledge_percentage,
                                                       "show_success_message":show_success_message, "is_dollar" : is_dollar}))

