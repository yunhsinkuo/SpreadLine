import pandas as pd
import numpy as np
from datetime import datetime
from itertools import groupby

import pandas as pd

def filter_time_by_ego(ego: str, data: pd.DataFrame) -> pd.DataFrame:
    timestamps = set(data['time'])
    for time, group in data.groupby(by='time'):
        nodes = group['source'].unique().tolist() + group['target'].unique().tolist()
        if ego not in nodes:
            timestamps.remove(time)
    #NOTE: later on the time extents would be computed to get the time array, which will fill in the missing timestamps with empty data in between.
    return data.copy().loc[data['time'].isin(timestamps), :]

def construct_egocentric_network(ego: str, data: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs an egocentric network for a given ego node in a given DataFrame of edges.

    Args:
        ego (str): The ego node for which to construct the egocentric network.
        data (pd.DataFrame): The DataFrame of edges from which to construct the egocentric network.

    Returns:
        pd.DataFrame: The DataFrame of edges in the egocentric network.
    """
    HOP_LIMIT = 2  # The maximum number of hops to include in the egocentric network.

    data = data.reset_index(drop=True)
    entities: list[str] = pd.concat([data['source'], data['target']]).unique().tolist()
    assert ego in entities, "Ego is not found in the data with the given time range."
    indices = pd.Index([])
    for _, entries in data.groupby(by='time'):
        waitlist: set = {ego}
        hop = 1
        while len(waitlist) != 0 and hop <= HOP_LIMIT:
            next_waitlist: list[str] = []
            for each in waitlist:
                sources = entries.loc[(data['target'] == each), :]
                targets = entries.loc[(data['source'] == each), :]
                candidates: list[str] = pd.concat([sources['source'], targets['target']]).unique().tolist()
                indices: pd.Index = indices.union(sources.index).union(targets.index)
                next_waitlist.extend(candidates)
            waitlist = set(next_waitlist) - set(waitlist)
            hop += 1
    # returning the two-hop ego network, proved to be correct
    return data.loc[indices, :]

def _get_entities(grouped_entities):
    return [each[0] for each in list(grouped_entities)]

def _order_within(constraints: list[tuple], entityColor: dict, ascending: bool=True) -> tuple[set, list[str]]:
    result = dict()
    sortedEntities: list[str] = []
    # ascending == false -> reverse == true -> descending -> ordering targets
    # ascending == true -> reverse == false -> ascending -> ordering sources
    constraints.sort(key=lambda x: x[2], reverse = (not ascending))

    entities = [(each[0], each[2]) for each in constraints] # source
    if not ascending: # target
        entities = [(each[1], each[2])  for each in constraints]

    if len(entities) == 0:
        return dict(result), sortedEntities
    # group the constraints, each is (source/target, weight), by the weight
    grouped_entities = groupby(entities, key=lambda x: x[1])
    counter = 0
    for weight, group in grouped_entities:
        entities = _get_entities(group)
        # Here we sort the entities further by their categories
        entities.sort(key=lambda x: entityColor.get(x, ''))
        if counter % 2 == 1: entities.reverse()
        result[weight] = entities 
        counter += 1
        sortedEntities.extend(result[weight])
    return result, sortedEntities

def find_within_constraints(entries: pd.DataFrame, ego: str, entityColor: dict) -> tuple[list[list[dict|str]], list[list[str]]]:
    raws: list[tuple] = entries.apply(lambda row: tuple(row[['source', 'target', 'weight']]), axis=1).tolist() 
    constraints = set()

    for (source, target, weight) in raws:
        bidirection: list[tuple] = list(filter(lambda x: x[:2] == (target, source), constraints))
        assert len(bidirection) <= 1, "The provided data should have been aggregated"
        if len(bidirection) == 1: # should behave so because we did drop_duplicates()
            otherWeight: int = bidirection[0][2]
            if otherWeight > weight: # overrides
                constraints.add(bidirection[0])
                if tuple([source, target, weight]) in constraints: constraints.remove(tuple([source, target, weight]))
                continue
            if otherWeight == weight: # If two are the same weight, then we ignore their relation constraints
                if tuple([source, target, weight]) in constraints: constraints.remove(tuple([source, target, weight]))
                continue 
        constraints.add(tuple([source, target, weight])) # keep this sorting
    
    sourceConstraints: list[tuple] = list(filter(lambda x: x[1] == ego, constraints))
    targetConstraints: list[tuple] = list(filter(lambda x: x[0] == ego, constraints))
    sourceGroup, sources = _order_within(sourceConstraints, entityColor, ascending=True)
    targetGroup, targets = _order_within(targetConstraints, entityColor, ascending=False)
    oneHops: list[str] = sources + targets

    remainedConstraints = list(constraints - set(sourceConstraints) - set(targetConstraints))
    # NOTE: this also enforces the two hop nodes to be ordered by the weight by default
    remainedConstraints.sort(key=lambda x: x[2], reverse=True) # let the weight to determine priority
    twoHopTops = []
    twoHopBottoms = []
    twoHops = []
    for (source, target, weight) in remainedConstraints:
        if source in oneHops and target in oneHops: continue
        if target in oneHops and source not in oneHops: # source is ego's two-hop neighbor
            if target in sources: # source -> target -> ego, i.e., this pair should be placed above the ego
                # (source, target) and (target, ego) should already exists
                if source not in twoHops: twoHopTops.append(source)
            elif target in targets: # ego -> target; source -> target; i.e., this pair should be placed below the ego, where source should be pushed further
                if source not in twoHops: twoHopBottoms.append(source)
        elif source in oneHops and target not in oneHops: # target is two-hop
            if source in sources: # source -> ego; source -> target; i.e., this pair should be placed above the ego, where target should be pushed further
                if target not in twoHops: twoHopTops.append(target)
            elif source in targets: # ego-> source -> target;
                if target not in twoHops: twoHopBottoms.append(target)
        twoHops = twoHopTops + twoHopBottoms

    
    order: list[list[str]] = [twoHopTops, sources, [ego], targets, twoHopBottoms] # a.k.a. hops
    result: list[list[dict|str]] = [twoHopTops, sourceGroup, [ego], targetGroup, twoHopBottoms]

    return result, order