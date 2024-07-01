import pandas as pd
import numpy as np
from SpreadLine.spreadline import SpreadLine
import itertools
import json

def computeAnimalSpreadLine():
    path = '../../case-studies/animal-health'
    SpreadLiner = SpreadLine()

    SpreadLiner.load(f'{path}/records.csv', config={
        'source': 'Source',
        'target': 'Target',
        'time': 'Date',
        'weight': 'Quantity',
    })
    SpreadLiner.load(f'{path}/sites.csv', config={
        'timestamp': '',
        'id': 'grower',
        'posX': 'longitude',
        'posY': 'latitude',
    }, key='content')
    SpreadLiner.load(f'{path}/status.csv', config={
        'time': 'date',
        'entity': 'entity',
        'context': 'context',
    }, key='node')
    SpreadLiner.load(f'{path}/sites.csv', config={
        'entity': 'grower',
        'color': 'color',
    }, key='line')
    SpreadLiner.center(ego='SI')
    result = SpreadLiner.fit(width=1800, height=1000) 
    result.update({"mode": "animal"})
    return result

def computeMetooSpreadLine():
    path = '../../case-studies/metoo'
    df = pd.read_csv(f'{path}/relations.csv')
    entities = pd.read_csv(f'{path}/entities.csv')
    network = _construct_ego_networks(df, 'Danny Masterson', time='Time', source='Source', target='Target')
    with open(f'{path}/groups.json', 'r') as f:
        groups = json.load(f)
    network['weight'] = df.apply(lambda row: row['ID'].count(',') + 1, axis=1)

    SpreadLiner = SpreadLine()
    SpreadLiner.load(network, config={
        'source': 'Source',
        'target': 'Target',
        'time': 'Time',
        'weight': 'weight',
    })
    SpreadLiner.load(entities, config={
        'entity': 'entity',
        'color': 'color',
    }, key='line')
    SpreadLiner.load(f'{path}/color.csv', config={
        'time': 'date',
        'entity': 'entity',
        'context': 'attitude',
    }, key='node')
    layout = pd.read_csv(f'{path}/layout.csv')
    SpreadLiner.load(layout, config={
        'timestamp': 'time',
        'id': 'name',
        'posX': 'posX',
        'posY': 'posY',
    }, key='content')

    SpreadLiner.center(ego='Danny Masterson')
    SpreadLiner.configure({'squeezeSameCategory': True, 
                           'bandStretch': [['2023-09-07', '2023-09-10'], ['2023-09-17', '2023-09-19']], 
                           'minimize': 'line'})
    result = SpreadLiner.fit(width = 2600, height = 500)
    network['time'] = network['time'].apply(lambda x: x.strftime('%Y-%m-%d'))
    result.update({"mode": "metoo", 'reference': network.to_dict(orient='records')})
    return result

def _remap_TM_affiliation(affiliation):
    if not isinstance(affiliation, str): return 'University of British Columbia, Canada'
    if 'British' in affiliation:
        return 'University of British Columbia, Canada'
    if 'Stanford' in affiliation or 'STANFORD' in affiliation:
        return 'Stanford University, USA'
    if 'Geometry Center' in affiliation:
        return 'Geometry Center, University of Minnesota, USA'
    return affiliation

def _remap_JH_affiliation(affiliation):
    if not isinstance(affiliation, str): return "University of Washington, USA"
    if "Berkeley" in affiliation:
        return "University of California, Berkeley, USA"
    if "PARC" in affiliation or "Palo Alto" in affiliation or "Xerox" in affiliation:
        return "Palo Alto Research Center, USA"
    if "Stanford" in affiliation:
        return "Stanford University, USA"
    if "Washington" in affiliation:
        return "University of Washington, USA"
    return affiliation


def _construct_ego_networks(data: pd.DataFrame, ego: str, HOP_LIMIT: int = 2, time: str = 'year', source: str = 'source', target: str = 'target') -> pd.DataFrame:
    # Note: make sure ego exists in each timepoint in data
    indices = pd.Index([])
    for _, entries in data.groupby(by=time): 
        waitlist: set = {ego}
        hop = 1
        while len(waitlist) != 0 and hop <= HOP_LIMIT:
            next_waitlist: list[str] = []
            for each in waitlist:
                sources = entries.loc[(data[target] == each), :]
                targets = entries.loc[(data[source] == each), :]
                candidates: list[str] = pd.concat([sources[source], targets[target]]).unique().tolist()
                indices: pd.Index = indices.union(sources.index).union(targets.index)
                next_waitlist.extend(candidates)
            waitlist = set(next_waitlist) - set(waitlist)
            hop += 1
    # returning the two-hop ego network, proved to be correct
    return data.loc[indices, :]

def _construct_author_network(ego, affiliation_remap, relationsPath = '../../case-studies/vis-author/relations.csv',
                              entitiesPath = '../../case-studies/vis-author/entities.csv', times=[]):
    INTERNAL_COLOR = '#FA9902'
    EXTERNAL_COLOR = '#166b6b'

    relations = pd.read_csv(relationsPath)
    relations['year'] = relations['year'].apply(lambda x: str(x))

    allEntities = pd.read_csv(entitiesPath)
    allEntities['year'] = allEntities['year'].apply(lambda x: str(x))
    if times != []: 
        allEntities = allEntities.loc[allEntities['year'].isin(times), :]
        relations = relations.loc[relations['year'].isin(times), :]
    egoStatus = allEntities.loc[allEntities['name'] == ego, ['affiliation', 'year']]
    egoStatus['affiliation'] = egoStatus['affiliation'].apply(lambda x: affiliation_remap(x))
    egoStatus = egoStatus.drop_duplicates()
    egoStatus = egoStatus.set_index('year').squeeze().to_dict()
    years = list(egoStatus.keys())

    relations = relations.loc[relations['year'].isin(years), :]
    # All the sources are first-authors
    network = _construct_ego_networks(relations, ego)

    # Remove those papers that ego wasn't even in
    for paperID, group in network.groupby(by='id'):
        nodes = group['source'].unique().tolist() + group['target'].unique().tolist()
        if ego not in nodes: network = network.drop(index=group.index)
    colorAssign = {}

    def get_affiliations(author, year):
        mask = (allEntities['name'] == author) & (allEntities['year'] == year)
        #print(allEntities.loc[mask, 'affiliation'].tolist())
        return allEntities.loc[mask, 'affiliation'].apply(lambda x: affiliation_remap(x)).unique()

    groupAssign = {}
    participation = {}
    for idx, row in network.iterrows():
        firstAuthor = row['source']
        author = row['target']
        year = row['year']
        egoAffiliations = get_affiliations(ego, year)
        #egoAffiliation = egoStatus[year]
        # [external-non-first, external-first, ego, internal-first, internal-non-first]
        if year not in groupAssign: groupAssign[year] = [set(), set(), set([ego]), set(), set()]
        if year not in colorAssign: colorAssign[year] = {}

        if author == ego:
            # ego is the non-first author
            affiliations = get_affiliations(firstAuthor, year)
            intersection = set(affiliations).intersection(egoAffiliations)
            color = INTERNAL_COLOR if len(intersection) != 0 else EXTERNAL_COLOR
            if len(intersection) != 0: groupAssign[year][3].add(firstAuthor)
            else: groupAssign[year][1].add(firstAuthor)
            if colorAssign[year].get(firstAuthor, None) is None: colorAssign[year][firstAuthor] = color

            allCollab = ((network['source'] == firstAuthor) | (network['target'] == firstAuthor))
            collab = ((network['source'] == firstAuthor) | (network['target'] == firstAuthor))# & (network['year'] == year)
        else: # either ego is the first author, or ego is the non-first author and this row is about others
            affiliations = get_affiliations(author, year)

            intersection = set(affiliations).intersection(egoAffiliations)
            color = INTERNAL_COLOR if len(intersection) != 0 else EXTERNAL_COLOR

            if color == INTERNAL_COLOR: groupAssign[year][4].add(author)
            else: groupAssign[year][0].add(author)

            if colorAssign[year].get(author, None) is None: colorAssign[year][author] = color

            collab = ((network['source'] == author) | (network['target'] == author))# & (network['year'] == year)

        network.at[idx, 'count'] = network.loc[collab, :]['id'].nunique()

    papers = network['id'].unique().tolist()

    for (key, groups) in groupAssign.items():
        pairIndices = list((i,j) for ((i,_),(j,_)) in itertools.combinations(enumerate(groups), 2))
        for pairIdx in pairIndices:
            if 2 in pairIdx: continue
            pair = [groups[pairIdx[0]], groups[pairIdx[1]]]
            if not pair[0].isdisjoint(pair[1]): 
                firstIdx = pairIdx[0]
                secondIdx = pairIdx[1]
                intersection = pair[0].intersection(pair[1])
                if firstIdx in [0, 4]: 
                    groupAssign[key][firstIdx] = pair[0] - intersection
                elif secondIdx in [0, 4]: 
                    groupAssign[key][secondIdx] = pair[1] - intersection
        newGroups = []
        
        for idx, group in enumerate(groups):
            if len(group) <= 1: 
                newGroups.append(list(group))
                continue
            newGroup = list(group)
            toBeReverse = False if idx in [0, 1] else True
            newGroup.sort(key=lambda x: network.loc[(network['source'] == x) | (network['target'] == x), :]['id'].nunique(), reverse=toBeReverse)
            newGroups.append(newGroup)
        groupAssign[key] = newGroups

    entities = network['source'].unique().tolist() + network['target'].unique().tolist()
    frames = []
    for entity in entities:
        for year in network['year'].unique():
            if colorAssign[year].get(entity, None) is None: continue
            frames.append({'entity': entity, 'color': colorAssign[year].get(entity)})
            break

    return network, pd.DataFrame(frames), groupAssign

def computeJHSpreadLine():
    SpreadLiner = SpreadLine()
    ego = "Jeffrey Heer"
    path = '../../case-studies/vis-author'
    network, lineColor, groups = _construct_author_network(ego, _remap_JH_affiliation)
    print(network.shape)
    SpreadLiner.load(network, config={
        'source': 'source',
        'target': 'target',
        'time': 'year',
        'weight': 'count',
    })
    SpreadLiner.load(lineColor, config={
        'entity': 'entity',
        'color': 'color',
    }, key='line')
    citations = pd.read_csv(f'{path}/citations.csv')
    papers = network['id'].unique().tolist() #133
    frames = []
    for paper in papers:
        group= citations.loc[citations['paperID'] == paper, :]
        for idx, row in group.iterrows():
            frames.append({'entity': row['name'], 'time': str(row['year']), 'context': int(row['citationcount'])})
    nodeContent = pd.DataFrame(frames).groupby(['entity', 'time']).agg({'context': 'sum'}).reset_index()
    SpreadLiner.load(nodeContent, config={
        'time': 'time',
        'entity': 'entity',
        'context': 'context',
    }, key='node')
    layout = pd.read_csv(f'{path}/Heer/content.csv')
    SpreadLiner.load(layout, config={
        'timestamp': 'year',
        'id': 'name',
        'posX': 'posX',
        'posY': 'posY',
    }, key='content')
    reference = pd.read_csv(f'{path}/Heer/content_reference.csv')


    SpreadLiner.center(ego=ego, timeDelta='year', timeFormat='%Y', groups=groups)
    SpreadLiner.configure({"squeezeSameCategory": True, "minimize": "wiggles"}) 
    result = SpreadLiner.fit(width = 2800, height = 1000)
    result.update({"mode": "author", 'reference': reference.to_dict(orient='records')})
    return result

def computeTMSpreadLine():
    SpreadLiner = SpreadLine()
    ego = 'Tamara Munzner'
    path = '../../case-studies/vis-author'

    network, lineColor, groups = _construct_author_network(ego, _remap_TM_affiliation)
    SpreadLiner.load(network, config={
        'source': 'source',
        'target': 'target',
        'time': 'year',
        'weight': 'citationcount',
    })
    SpreadLiner.load(lineColor, config={
        'entity': 'entity',
        'color': 'color',
    }, key='line')
    citations = pd.read_csv(f'{path}/citations.csv') #97 papers
    papers = network['id'].unique().tolist()
    
    frames = []
    for paper in papers:
        group= citations.loc[citations['paperID'] == paper, :]
        for idx, row in group.iterrows():
            frames.append({'entity': row['name'], 'time': str(row['year']), 'context': int(row['citationcount'])})
    nodeContent = pd.DataFrame(frames).groupby(['entity', 'time']).agg({'context': 'sum'}).reset_index()
    SpreadLiner.load(nodeContent, config={
        'time': 'time',
        'entity': 'entity',
        'context': 'context',
    }, key='node')
    layout = pd.read_csv(f'{path}/Munzner/content.csv')
    SpreadLiner.load(layout, config={
        'timestamp': 'year',
        'id': 'name',
        'posX': 'posX',
        'posY': 'posY',
    }, key='content')
    reference = pd.read_csv(f'{path}/Munzner/content_reference.csv')


    SpreadLiner.center(ego=ego, timeDelta='year', timeFormat='%Y', groups=groups)
    SpreadLiner.configure({"squeezeSameCategory": True, "minimize": "wiggles"})

    result = SpreadLiner.fit(width = 2700, height = 1000)
    result.update({"mode": "author", 'reference': reference.to_dict(orient='records')})
    return result
