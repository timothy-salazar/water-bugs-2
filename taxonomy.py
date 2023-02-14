from pathlib import Path
import requests
import xml.etree.ElementTree as ET
import os
import time
import pandas as pd
import re

# this will raise an error if you don't have these environment variables set.
EMAIL=os.environ['NCBI_EMAIL_ADDR']
TOOL=os.environ['NCBI_TOOL_NAME']
DATA_PATH=os.environ['NCBI_DATA_PATH']
SLEEP_INTERVAL=.5
RETURN_RANKS=['species','genus','family','order']

def thing(d):
    s = re.sub('_sp|_adult|_larva', '', d).split('_')
    if len(s) > 1:
        return '+'.join([s[0], s[-1]])
    else:
        return s[0]

def get_names_from_dataset(path:str):
    """ Input:
            path: str - the path to the directory containing the dataset.
                This assumes that the images are stored in directories whose
                names are formatted as "Genus_species".
        Output:
            species_list: list of strings - the names of the species represented
                in the dataset. These will be of the form "Genus+species"
    """
    p = Path(path)
    species_list = [thing(x.name) for x in p.iterdir() if x.is_dir()]
    return species_list

def get_id_from_name(species:str):
    """ Input:
            species: str - the name of the species whose ID we want. Should
                be formatted as "Genus+species"
        Output:
            id_list: list of strings - a list containing the ids returned by
                the search.
    """
    print('Starting species:', species)
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    payload = {
            'mail': EMAIL,
            'tool': TOOL, 
            'db':'taxonomy', 
            'term':species,
            'rettype':'uilist',
            'retmode':'json'
        }
    req = requests.get(url, params=payload)
    req.raise_for_status()
    id_list = req.json()['esearchresult']['idlist']
    if len(id_list) > 1:
        raise ValueError(f'Expected API to return one id, but it returned {len(id_list)} ids instead')
    if not id_list:
        raise ValueError(f'Request returned empty id_list: {req.text}')
    return id_list[0]

def get_id_from_dir(species:str):
    """ Input:
            species: str - the name of the species whose ID we want. Should
                be formatted as "Genus+species"
        Output:
            id_list: list of strings - a list containing the ids returned by
                the search.
    """
    species = thing(species)
    print('Starting species:', species)
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    payload = {
            'mail': EMAIL,
            'tool': TOOL, 
            'db':'taxonomy', 
            'term':species,
            'rettype':'uilist',
            'retmode':'json'
        }
    req = requests.get(url, params=payload)
    req.raise_for_status()
    id_list = req.json()['esearchresult']['idlist']
    if len(id_list) > 1:
        raise ValueError(f'Expected API to return one id, but it returned {len(id_list)} ids instead')
    if not id_list:
        raise ValueError(f'Request returned empty id_list: {req.text}')
    return id_list[0]

def get_taxon_dict(
        taxid:str, 
        filter_list:list=None, 
        human_readable:bool=True,
        prefix:str=''
    ):
    """ Input:
            taxid: str - the id of the species we want to get taxonomic info
                about
            filter_list: list of strings - contains the names of the ranks
                we want to return. For example: if filter_list = ['genus'],
                this function will return a dictionary that only includes an
                entry for genus.
                If an item in filter_list is not returned by the API, an entry
                will not be created. In the example above, if no 'genus' entry
                is returned by the API this function will return an empty dict.
        Output:
            taxonomy_dict: dict - contains taxonomic information about the
                species indicated by 'taxid' (kingdom, phylum, class, etc.)
    """
    taxonomy_dict = dict()
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    payload = {
        'mail': EMAIL,
        'tool': TOOL, 
        'db':'taxonomy', 
        'id':taxid}
    r = requests.get(url, params=payload)
    root = ET.fromstring(r.content)
    taxonomy_dict = stuff(root[0], taxonomy_dict, human_readable=human_readable, prefix=prefix)

    # Get every other taxon in the species' lineage
    lineage = root[0].find('LineageEx')
    taxon = lineage.findall('Taxon')
    # get_rank = lambda taxa: taxa.find('Rank').text
    # get_name = lambda taxa: taxa.find('ScientificName').text
    # taxonomy_dict = {get_rank(taxa):get_name(taxa) for taxa in taxon}

    # NOTE: there are multiple entries with the rank "clade". Because this
    # makes a dict, only one of these will be present in taxonomy_dict (if clade
    # is included in 'filter_list' - it's a moot point otherwise since the clade
    # entries will be dropped)
    
    for taxa in taxon:
        taxonomy_dict = stuff(taxa, taxonomy_dict, filter_list, human_readable, prefix=prefix)
        # rank = taxa.find('Rank').text
        # if filter_list and rank in filter_list:
        #     if human_readable:
        #         taxonomy_dict[rank] = taxa.find('ScientificName').text
        #     else:
        #         taxonomy_dict[rank] = taxa.find('TaxId').text
    return taxonomy_dict

def stuff(
        taxa, 
        taxonomy_dict, 
        filter_list:list=None, 
        human_readable:bool=True,
        prefix:str=''
        ):
    """
    """
    rank = taxa.find('Rank').text
    if human_readable:
        name = taxa.find('ScientificName').text
    else:
        name = taxa.find('TaxId').text
    # We only filter if filter list is not none
    if filter_list and rank in filter_list:
        taxonomy_dict[prefix+rank] = name
    if not filter_list:
         taxonomy_dict[prefix+rank] = name 
    return taxonomy_dict
        

# def taxonomy_from_name(species:str, filter_list:list=None, human_readable=True):
#     taxon_id = get_id_from_name(species)
#     time.sleep(SLEEP_INTERVAL)
#     tax_dict = get_taxon_dict(taxon_id)
#     time.sleep(SLEEP_INTERVAL)
#     return tax_dict

# def get_df(human_readable=True):
#     species_list = get_names_from_dataset(DATA_PATH)
#     taxonomy_list = []
#     for species in species_list:
#         taxon_id = get_id_from_name(species)
#         time.sleep(SLEEP_INTERVAL)
#         tax_dict = get_taxon_dict(taxon_id, filter_list=RETURN_RANKS, human_readable=human_readable)
#         time.sleep(SLEEP_INTERVAL)
#         # if human_readable:
#         #     tax_dict['species'] = species
#         # else:
#         #     tax_dict['species'] = taxon_id
#         # tax_dict['species'] = species
#         # tax_dict['taxid'] = taxon_id
#         taxonomy_list.append(tax_dict)
#     return pd.DataFrame.from_records(taxonomy_list)

def name_to_tax(species, human_readable=True):
    taxon_id = get_id_from_name(thing(species))
    time.sleep(SLEEP_INTERVAL)
    tax_dict = get_taxon_dict(
                taxon_id, 
                filter_list=RETURN_RANKS, 
                human_readable=human_readable,
            )
    time.sleep(SLEEP_INTERVAL)
    return tax_dict
    
def n2req(species):
    taxon_id = get_id_from_name(thing(species))
    time.sleep(SLEEP_INTERVAL)
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    payload = {
        'mail': EMAIL,
        'tool': TOOL, 
        'db':'taxonomy', 
        'id':taxon_id}
    r = requests.get(url, params=payload)
    return r

def n2tree(species):
    r = n2req(species)
    root = ET.fromstring(r.content)
    sdfa(root[0])
    lineage = root[0].find('LineageEx')
    taxon = lineage.findall('Taxon')
    for taxa in taxon:
        sdfa(taxa)

def sdfa(taxa):
    rank = taxa.find('Rank').text
    name = taxa.find('ScientificName').text
    print(rank.ljust(20), ':', name)

def junk():
    labels = []
    taxonomy_list = []
    species_list = []
    for directory in os.walk(DATA_PATH):
        path, dirs, files = directory
        if files:
            dir_name = os.path.split(path)[-1]
            species = thing(dir_name)
            taxon_id = get_id_from_name(species)
            species_list.append(species)
            time.sleep(SLEEP_INTERVAL)
            tax_dict_hr = get_taxon_dict(
                    taxon_id, 
                    filter_list=RETURN_RANKS, 
                    human_readable=True,
                    prefix='hr_'
                )
            tax_dict = get_taxon_dict(
                    taxon_id, 
                    filter_list=RETURN_RANKS, 
                    human_readable=False
                )
            # tax_dict = {k:int(v) for k,v in tax_dict.items()}
            labels += [[int(v) for v in tax_dict.values()]] * len(files)
            tax_dict['path'] = path
            tax_dict['dir_name'] = dir_name
            tax_dict['taxon_id'] = int(taxon_id)
            tax_dict |= tax_dict_hr
            taxonomy_list.append(tax_dict)
            time.sleep(SLEEP_INTERVAL)
            



if __name__ == '__main__':
    pass
