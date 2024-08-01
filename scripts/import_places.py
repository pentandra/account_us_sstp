#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
from __future__ import print_function

import csv
import os
import sys
from argparse import ArgumentParser

try:
    from urllib.error import HTTPError
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen, HTTPError

from io import BytesIO, TextIOWrapper

try:
    import argcomplete
except ImportError:
    argcomplete = None

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)

DIVISIONS = {
    'D1': ['09', '23', '25', '33', '44', '50'],
    'D2': ['34', '36', '42'],
    'D3': ['17', '18', '26', '39', '55'],
    'D4': ['19', '20', '27', '29', '31', '38', '46'],
    'D5': ['10', '11', '12', '13', '24', '37', '45', '51', '54'],
    'D6': ['01', '21', '28', '47'],
    'D7': ['05', '22', '40', '48'],
    'D8': ['04', '08', '16', '30', '32', '35', '49', '56'],
    'D9': ['02', '06', '15', '41', '53'],
    }
REGION2PARENT = {c: p for p, r in DIVISIONS.items() for c in r}

def _progress(iterable):
    if ProgressBar:
        pbar = ProgressBar(
            widgets=[SimpleProgress(), Bar(), ETA()])
    else:
        pbar = iter
    return pbar(iterable)

def _get_language_codes():
    Language = Model.get('ir.lang')
    languages = Language.find([('translatable', '=', True)])
    for l in languages:
        yield l.code

def fetch(url):
    sys.stderr.write('Fetching')
    try:
        responce = urlopen(url)
    except HTTPError as e:
        sys.exit("\nError downloading %s: %s" % (url, e.reason))
    data = responce.read()
    print('.', file=sys.stderr)
    return data

def get_states(code):
    Place = Model.get('census.place')
    return {c.code_fips: c for c in Place.find([('country.code', '=', code)])}

def update_states(code, states):
    print("Update states", file=sys.stderr)
    CensusRegion = Model.get('census.region')
    Place = Model.get('census.place')
    Country = Model.get('country.country')
    Subdivision = Model.get('country.subdivision')

    def get_country(code):
        country = countries.get(code)
        if not country:
            try:
                country, = Country.find([('code', '=', code)])
            except ValueError:
                sys.exit("Error missing country with code %s" % code)
            countries[code] = country
        return country
    countries = {}

    def get_subdivision(country, code):
        code = '%s-%s' % (country, code)
        subdivision = subdivisions.get(code)
        if not subdivision:
            try:
                subdivision, = Subdivision.find([('code', '=', code)])
            except ValueError:
                return
            subdivisions[code] = subdivision
        return subdivision
    subdivisions = {}

    country = get_country(code)

    code2region = {a.code: a for a in CensusRegion.find([])}

    data = fetch('https://www2.census.gov/geo/docs/reference/codes2020/national_state2020.txt')
    f= TextIOWrapper(BytesIO(data), encoding='utf-8')

    records = []
    for row in _progress(list(csv.DictReader(f, delimiter='|'))):
        code_fips = row['STATEFP']
        if code_fips in states:
            record = states[code_fips]
        else:
            record = Place(code_fips=code_fips, country=country)
        record.name = row['STATE_NAME']
        record.code_gnis = int(row['STATENS'])
        record.subdivision = get_subdivision(country.code, row['STATE'])
        record.region = code2region.get(REGION2PARENT.get(code_fips))

        records.append(record)

    Place.save(records)
    return {c.code_fips: c for c in records}

def get_counties(code):
    Place = Model.get('census.place')
    return {(c.subdivision.code, c.code_fips): c for c in Place.find([])}
#    return {(c.subdivision.code, c.code_fips): c for c in Place.find([('subdivision.code', '=', code)])}

def update_counties(states, counties):
    print("Update counties", file=sys.stderr)
    ClassCode = Model.get('census.class_code')
    Place = Model.get('census.place')

    # 'https://www2.census.gov/geo/docs/reference/codes2020/cou/st49_ut_cou2020.txt' 
    data = fetch('https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt')
    f= TextIOWrapper(BytesIO(data), encoding='utf-8')

    class_codes = {c.code: c for c in ClassCode.find([])}
    unknown_class_codes = set()
    records = []
    for row in _progress(list(csv.DictReader(f, delimiter='|'))):
        state = states[row['STATEFP']]
        subdivision_code = state.subdivision.code
        county_fips = row['COUNTYFP']
        if (subdivision_code, county_fips) in counties:
            record = counties[(subdivision_code, county_fips)]
        else:
            record = Place(code_fips=county_fips,
                    subdivision=state.subdivision, country=state.country)
        record.name = row['COUNTYNAME']
        record.code_gnis = int(row['COUNTYNS'])
        class_code = row['CLASSFP']
        record.parent = state
        record.region = state.region
        if class_code in class_codes:
            record.class_code = class_codes[class_code]
        else:
            record.class_code = None
            if class_code not in unknown_class_codes:
                print("Unknown class code: %s" % class_code,
                        file=sys.stderr)
                unknown_class_codes.add(class_code)
        records.append(record)

    Place.save(records)
    return {(c.subdivision.code, c.code_fips): c for c in records}

def get_places(code):
    Place = Model.get('census.place')
    #return {c.code_fips: c for c in Place.find([('level', '=', level)])}
    return {(c.subdivision.code, c.code_fips): c for c in Place.find([])}

def update_places(states, counties, places):
    print("Update places", file=sys.stderr)
    ClassCode = Model.get('census.class_code')
    Place = Model.get('census.place')

    # 'https://www2.census.gov/geo/docs/reference/codes2020/place_by_cou/st49_ut_place_by_county2020.txt'
    data = fetch('https://www2.census.gov/geo/docs/reference/codes2020/national_place_by_county2020.txt')
    f= TextIOWrapper(BytesIO(data), encoding='utf-8')

    class_codes = {c.code: c for c in ClassCode.find([])}
    unknown_class_codes = set()
    records = []
    for row in _progress(list(csv.DictReader(f, delimiter='|'))):
        state = states[row['STATEFP']]
        subdivision_code = state.subdivision.code
        county = counties[(subdivision_code, row['COUNTYFP'])]
        place_fips = row['PLACEFP']
        if (subdivision_code, place_fips) in places:
            record = places[(subdivision_code, place_fips)]
        else:
            record = Place(code_fips=place_fips,
                    subdivision=state.subdivision, country=state.country)
        record.name = row['PLACENAME']
        record.code_gnis = int(row['PLACENS'])
        class_code = row['CLASSFP']
        record.parent = county
        record.region = state.region
        if class_code in class_codes:
            record.class_code = class_codes[class_code]
        else:
            record.class_code = None
            if class_code not in unknown_class_codes:
                print("Unknown class code: %s" % class_code,
                        file=sys.stderr)
                unknown_class_codes.add(class_code)
        records.append(record)

    Place.save(records)

def main(database, codes, config_file=None):
    config.set_trytond(database, config_file=config_file)
    with config.get_config().set_context(active_test=False):
        do_import(codes)

def do_import(codes):
    states = get_states('US')
    states = update_states('US', states)
    #translate_states(states)

    for code in codes:
        print(code, file=sys.stderr)
        code = 'US-%s' % code.upper()
        counties = get_counties(code)
        counties = update_counties(states, counties)
        #translate_counties(counties)
        places = get_places(code)
        update_places(states, counties, places)

def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('codes', nargs='+')
    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    main(args.database, args.codes, args.config_file)


if __name__ == '__main__':
    run()
