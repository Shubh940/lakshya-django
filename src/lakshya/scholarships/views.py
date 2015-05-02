# Create your views here.
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from accounts.models import DonationFund
from scholarships.models import Scholar

def get_scholar_year_list():
    scholars = Scholar.objects.all().order_by("-person__year_of_passing")
    scholar_year_dict = {}
    for scholar in scholars:
        if scholar.person.year_of_passing in scholar_year_dict:
            scholar_year_dict[scholar.person.year_of_passing].append(scholar)
        else:
            scholar_year_dict[scholar.person.year_of_passing] = [scholar, ]
    scholar_year_list = []
    for year in sorted(scholar_year_dict):
        scholar_year_list.append((year, scholar_year_dict[year]))
    return scholar_year_list    
        
def scholarships_home(request):
    funding_partners = DonationFund.objects.all()   
    context = {"scholar_year_list" : get_scholar_year_list(), "funding_partners_list" : funding_partners}
    return render_to_response("scholarships_home.html", 
                              RequestContext(request, context))

def funding_partners_list(request):
    context = {}
    funding_partners = DonationFund.objects.all()
    funding_partners_list = [] #list of lists
    for funding_partner in funding_partners:
        funding_partners_list.append((funding_partner,Scholar.objects.filter(donation_fund=funding_partner),))        
    context["funding_partners_list"] = funding_partners_list
    return render_to_response("scholarships_funding_partners.html", 
                              RequestContext(request, context))

def get_scholarships_list(request, scholar_id):
    scholar_list = Scholar.objects.all()
    scholar_id = scholar_id or 16  # For some strange reason this has been hardcoded in the past to 16 but was broken
    context = {"scholar_year_list" : get_scholar_year_list(), "scholar_list" : scholar_list, "show_scholar": scholar_id, }
    return render_to_response("scholars_list.html", 
                              RequestContext(request, context))
