from pathlib import Path
import requests
# because xml is dangerous
from defusedxml import ElementTree as ET
from xml.etree.ElementTree import Element
from collections import defaultdict
import os
import time
import pandas as pd
import re
import json
from tqdm import tqdm

# this will raise an error if you don't have these environment variables set.
EMAIL=os.environ['NCBI_EMAIL_ADDR']
TOOL=os.environ['NCBI_TOOL_NAME']
DATA_PATH=os.environ['NCBI_DATA_PATH']
SLEEP_INTERVAL=.5
RETURN_RANKS=['order','family','genus','species']
BASE_URL='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
JSON_PATH=os.environ['JSON_PATH']

def make_req(
        url: str,
        payload: dict,
        max_attempts: int=3,
        timeout: int=10):
    """ Input:
            url: str - the url we want to make the request to
            payload: dict - contains the values we want to pass as parameters 
                in the URL's query string
            max_attempts: int - the number of retries to make before giving up
            timeout: int - the length of time in seconds to wait before assuming
                something went wrong with the request
        Output:
            req: requests.Response - the response returned by the NCBI API
    """
    for i in range(max_attempts + 1):
        try:
            req = requests.get(
                url,
                params=payload,
                timeout=timeout)
            req.raise_for_status()
            return req
        except requests.HTTPError as e:
            if i == max_attempts:
                raise e
            print('connection issue. Waiting 1 second and trying again...')
            time.sleep(1)
    raise requests.HTTPError
    
    
def esearch_req(species: str):
    """ Input:
            species: str - the name of the species whose ID we want.
        Output:
            req: requests.Response - the response returned by the esearch
                endpoint of the NCBI API for the species in question.

    The NCBI eutils esearch endpoint can return a list of UIDs that match a
    query.
    Docs are here:
    https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch
    """
    url = BASE_URL + 'esearch.fcgi'
    payload = {
            'mail': EMAIL,
            'tool': TOOL, 
            'db':'taxonomy', 
            'term':species,
            'rettype':'uilist',
            'retmode':'json'
        }
    req = make_req(url, payload)
    return req

def efetch_req(taxid: int):
    """ Input:
            taxid: int - the taxon ID that we want more information on
        Output:
            req: requests.Response - the response returned by the efetch
                endpoint of the NCBI API for the taxon in question.
    
    The NCBI eutils efetch endpoint returns data records for a UID or list of
    UIDs.
    Docs are here:
    https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
    """
    url = BASE_URL + 'efetch.fcgi'
    payload = {
        'mail': EMAIL,
        'tool': TOOL, 
        'db':'taxonomy', 
        'id':taxid}
    req = make_req(url, payload)
    return req
    

def species_to_id(species: str, verbose: bool=False):
    """ Input:
            species: str - the name of the species whose ID we want.
            verbose: bool - if true, it will print each species name as it is started
        Output:
            int - the taxon id for the given species
    """
    if verbose:
        print('Starting species:', species)
    req = esearch_req(species)
    id_list = req.json()['esearchresult']['idlist']
    if len(id_list) > 1:
        raise ValueError(f'Expected API to return one id, but it returned {len(id_list)} ids instead')
    if not id_list:
        raise ValueError(f'Request returned empty id_list: {req.text}')
    if not id_list[0].isdigit():
        raise ValueError(f'Expected API to return one taxon id consisting of all decimal \
        characters. Returned {id_list[0]} instead.')
    return int(id_list[0])

def etree_from_id(taxid: int):
    """ Input:
            taxid: int - an NCBI taxonomic id. 
        Output:
            tree: defusedxml.ElementTree - an element tree containing the information returned by the
                NCBI efetch API on the lineage of the organism.
    """
    req = efetch_req(taxid)
    tree = ET.fromstring(req.content)
    return tree

def etree_to_dict(root: ET):
    """ Input:
            root: defusedxml.ElementTree - an xml document as returned by the NCBI API efetch endpoint.
        Output:
            taxon_info: dict - the keys are:
                - rank: the rank of the organism, i.e. "order", "phylum", etc.
                - sci_name: the scientific name of the organism
                - taxon_id: the taxonomic id (an int)
                - lineage: a list of dicts. The keys are:
                    - rank:
                    - sci_name: 
                    - taxon_id: 
    Note: Within taxon_info we have the lineage dictionary, which is a list of dicts. 
    We're using a list of dicts because some ranks (specifically "clade") can appear multiple
    times.
    I decided to preserve all of the lineage data at this stage and filter out unused entries
    further down the line, so it will be easy to rework - just in case I find a use for the extra
    data somewhere.
    """
    # This gets us the rank, scientific name, and taxon id for the organism
    root_taxon = root.find('Taxon')
    rank, taxon_info = parse_taxon_element(root_taxon)
    taxon_info['rank'] = rank
    
    # This gets a list of the taxa in the organism's lineage and then creates
    # a dictionary of lists, where each entry is a dict containing scientific
    # name and taxonomic id
    lineage = defaultdict(list)
    taxa = root_taxon.find('LineageEx').findall('Taxon')
    for taxon in taxa:
        rank, info = parse_taxon_element(taxon)
        lineage[rank].append(info)
        
    taxon_info['lineage'] = lineage
    return taxon_info

def parse_taxon_element(taxon: Element):
    ''' Input:
            taxon: Element - the 'Taxon' element from the element tree which 
                we retrieved from the NCBI API
        Output:
            (rank, info): a tuple. "rank" is the rank of the element (i.e. "order", 
                "phylum", etc.), and "info" is a dictionary containing the 
                scientific name and taxon id for that rank.
    '''
    rank = taxon.find('Rank').text
    info = {
        'sci_name': taxon.find('ScientificName').text,
        'taxon_id': int(taxon.find('TaxId').text)
    }
    return rank, info

def species_to_dict(species, verbose: bool=False):
    ''' Input:
            species: str - the species we're interested in
        Output:
            tax_dict: dict - a dictionary containing the taxonomy data about
                "species" which was returned by the NCBI API
    '''
    taxid = species_to_id(species, verbose)
    tree = etree_from_id(taxid)
    tax_dict = etree_to_dict(tree)
    return tax_dict

def preprocess_name(dir_name: str):
    """ Input:
            dir_name: str - the name of a directory. This name should correspond
                to the name of an organism. i.e. 'Asellus_aquaticus', 'Chelifera', 
                'Ephemerella_aroni_aurivillii', etc.
        Output:
            str - the name of the organism, processed to obviate the issues I ran
                into with the single dataset I'm working with right now:
                    - organism names that end with "_sp", "_adult", or "_larva"
                    - organism names that contain more than 2 parts (this may be due
                      to ambiguity - I might reexamine this later)
    
    This isn't perfect, nor is it magic. 
    If there are misspelled names you'll have to go in and change them.
    """
    parts = re.sub('_sp|_adult|_larva', '', dir_name).split('_')
    if len(parts) > 1:
        return '+'.join([parts[0], parts[-1]])
    else:
        return parts[0]

def get_names_from_dataset(path: str):
    """ Input:
            path: str - the path to the directory containing the dataset.
                This assumes that the images are stored in directories whose
                names are formatted as "Genus_species".
        Output:
            species_list: list of strings - the names of the directories.
    """
    p = Path(path)
    species_list = [x.name for x in p.iterdir() if x.is_dir()]
    return species_list
    
def get_taxon_data(json_path: str):
    """ Input:
            json_path: str - the path of the json file in which we want to store
                our taxon data. If the file doesn't exist it will be created.
            typo_path: str - the path to a json file containing a dictionary
                that maps the names of directories that have been misspelled to
                corrected versions.
                I'm doing this as a dictionary in a separate json file instead
                of the simpler option of just changing the name of the directory
                manually because I might need to wipe the data - this happened 
                once when an image got corrupted by Tensorflow and it was easier
                to just wipe the directory and unzip it again.
                It's not just a dict at the top of the other json doc for
                similar reasons.
        Output:
            taxon_data: dict - a dictionary in which the keys are the names of
                directories, and the values are dictionaries containing the
                taxonomic lineage information returned by the API.
    """
    p = Path(json_path)
    if p.exists():
        with p.open() as f:
            taxon_data = json.load(f)
    else:
        taxon_data = dict()
    
    directory_names = set(get_names_from_dataset(DATA_PATH))
    new_directories = directory_names.difference(taxon_data.keys())
    failed_to_retrieve = list()
    print(f'Found {len(directory_names)} directories:')
    print(f'\t- {len(directory_names)-len(new_directories)} directories already\
         saved to json')
    print(f'\t- {len(new_directories)} new directories to retrieve data for\n')
    
    progress_bar = tqdm(new_directories)
    for dir_name in progress_bar:
        progress_bar.set_description(desc=dir_name.rjust(20, '-')[:20])
        try:
            # We want a dictionary where the keys are the names of directories,
            # so we only clean up the directory name with preprocess_name() and
            # get "organism_name" to make the API call
            organism_name = preprocess_name(dir_name)
            taxon_dict = species_to_dict(organism_name)
            taxon_data[dir_name] = taxon_dict
        except ValueError:
            print(f'Failed to retrieve data for directory "{dir_name}"')
            failed_to_retrieve.append(dir_name)

    # Save data back to the 
    with open(json_path, 'w') as f:
        json.dump(taxon_data, f)
    print(f'\nData for {len(new_directories) - len(failed_to_retrieve)} \
        directories successfully retrieved')
    print(f'Failed to retrieve {len(failed_to_retrieve)} directories:')
    print(failed_to_retrieve)
    return taxon_data

def dict_from_path(file_path: str):
    """ Input:
            file_path: str - the path to a file containing json data. 
        Output:
            a dictionary containing the data in the file specified by 
            "file_path". If the file does not exist, an empty dictionary is
            returned instead.
    """
    path = Path(file_path)
    if path.exists():
        with path.open() as f:
            return json.load(f)
    else:
        return dict()

def handle_typo(original, corrected, json_path):
    organism_name = preprocess_name(corrected)
    taxon_dict = species_to_dict(organism_name)
    taxon_data = dict_from_path(json_path)
    taxon_data[original] = taxon_dict
    with open(json_path, 'w') as f:
        json.dump(taxon_data, f)

if __name__ == '__main__':
    get_taxon_data(JSON_PATH)
