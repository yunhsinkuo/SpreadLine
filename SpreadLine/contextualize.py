import pandas as pd
import numpy as np
from scipy.stats import norm, cauchy
from sklearn import preprocessing
from sklearn.decomposition import PCA, SparsePCA

# missing: closest | ignore
#TODO: update the structure
def contextualizing(liner, normalize: bool=True, centered: bool=False):
    config = liner._content_config
    ego = liner.ego
    layout = pd.DataFrame([], columns=['entity', 'posX', 'posY', 'timestamp'])
    # When the content is not provided.
    if liner._content is None: 
        layout.set_index(keys=['entity', 'timestamp'], inplace=True)
        return {'layout': layout}

    entitiy_match = liner._content['id'].apply(lambda x: x in liner.entities_names)
    content = liner._content.loc[entitiy_match, :]

    layout = _collect_profiles(liner, content, config)
    layout['label'] = -1
    layout = layout.loc[:, ['id', 'posX', 'posY', 'timestamp', 'label']]
    layout = layout.rename(columns={'id': 'entity'})

    if normalize: layout = normalize_layout(layout)
    if centered: layout = center_layout(layout, ego)
    layout.set_index(keys=['entity', 'timestamp'], inplace=True)
    return {'layout': layout}


def _collect_profiles(liner, content: pd.DataFrame, config: dict, missing: str='closest'):
    profiles = []
    for session in liner.sessions:
        time = liner._all_timestamps[session.timestamp]
        entities = session.print_entities()
        for entity in entities:
            candidates = content.loc[(content['id'] == entity), :].drop_duplicates() 
            if candidates.empty: continue
            if config['dynamic'] == True:
                match = candidates.loc[(candidates['timestamp'] == time), :]
                if match.empty and missing == 'closest':
                    bisectIdx = candidates['timestamp'].searchsorted(time, side='left') - 1
                    match = candidates.reset_index(drop=True).iloc[bisectIdx, :].squeeze()
            elif config['dynamic'] == False:
                if candidates.shape[0] > 1: raise ValueError("Multiple matches when the static layout is specified")
                match = candidates
            match = match.squeeze().to_dict()
            match.update({'timestamp': session.timestamp})
            profiles.append(match)
    return pd.DataFrame(profiles)
    

def deprecated_contextualizing(liner, missing: str='closest', centered: bool=False):
    config = liner._content_config
    ego = liner.ego
    layout = pd.DataFrame([], columns=['entity', 'posX', 'posY', 'timestamp'])
    loadings = None
    # empty content handling
    if liner._content is None: 
        layout.set_index(keys=['entity', 'timestamp'], inplace=True)
        return {'layout': layout, 'loadings': loadings}

    entitiy_match = liner._content['id'].apply(lambda x: x in liner.entities_names)
    content = liner._content.loc[entitiy_match, :]
    nodeContext: pd.DataFrame = liner._node_color # node color
    normalize = True

    profiles = []
    for session in liner.sessions:
        date = liner._all_timestamps[session.timestamp]
        entities = session.print_entities()
        for entity in entities:
            candidates = content.loc[(content['id'] == entity), :].drop_duplicates() 
            if candidates.empty: continue # no available data
            if config['dynamic'] == True:
                match = candidates.loc[(candidates['timestamp'] == date), :]
                if match.empty and missing == 'closest':
                    bisectIdx = candidates['timestamp'].searchsorted(date, side='left') - 1
                    match = candidates.reset_index(drop=True).iloc[bisectIdx, :].squeeze()
                match = match.squeeze()
            elif config['dynamic'] == False:
                if candidates.shape[0] > 1: raise ValueError("Multiple matches when the static layout is specified")
                match = candidates.squeeze()
            match = match.to_dict()
            match.update({'timestamp': session.timestamp, 'date': date})
            profiles.append(match)

    if config['generated'] == False:   
        layout, loadings = generate_layout(pd.DataFrame(profiles))
    else:
        layout = pd.DataFrame(profiles)
        layout['label'] = -1
        #layout['label'] = layout.apply(lambda x: find_context(x, nodeContext), axis=1)
        layout = layout.loc[:, ['id', 'posX', 'posY', 'timestamp', 'label']]
        layout = layout.rename(columns={'id': 'entity'})

    if normalize: layout = normalize_layout(layout)
    if centered: layout = center_layout(layout, ego)
    layout.set_index(keys=['entity', 'timestamp'], inplace=True)
    #print(layout)
    return {'layout': layout, 'loadings': loadings}

def _deprecated_find_context(row, nodeContext):
    if nodeContext is None: return -1
    exactMask = (nodeContext['time'] == row['date']) & (nodeContext['entity'] == row['id'])
    exact = nodeContext.loc[exactMask].squeeze()
    return exact['context']

def _distort_to_fit(scaled: float):
    return scaled
    if scaled < 0: return max(0, scaled)
    return min(1, scaled)

def center_layout(layout, ego):
    egoEntries = layout.loc[layout['entity'] ==  ego, :]
    uniqueEgo = egoEntries.loc[:, ['posX', 'posY']].value_counts()
    if uniqueEgo.size != 1: raise TypeError("The layout is dynamic, centering is not recommended due to information loss")
    center = uniqueEgo.index.tolist()[0]
    layout['posX'] = layout['posX'].apply(lambda x: _distort_to_fit(x - center[0] + 0.5))# - center[0] + 0.5
    layout['posY'] = layout['posY'].apply(lambda x: _distort_to_fit(x - center[1] + 0.5))
    return layout

def normalize_layout(layout: pd.DataFrame):
    layout['posX'] = layout['posX'] - layout['posX'].min()
    layout['posX'] = layout['posX'] / layout['posX'].max()
    layout['posY'] = layout['posY'] - layout['posY'].min()
    layout['posY'] = layout['posY'] / layout['posY'].max()
    return layout

#deprecated
def generate_layout(data: pd.DataFrame, generator = None):
    entities, timestamps = data['id'], data['timestamp']
    data = data.drop(columns=['id', 'timestamp'])
    feature_names = data.columns
    data = data.to_numpy()
    scaler = preprocessing.StandardScaler()
    standardized_data = scaler.fit_transform(data)
    if generator is None:
        generator = SparsePCA(n_components=2, random_state=0)
    embeddings = generator.fit_transform(standardized_data)
    PCs = generator.components_.T
    loadings = pd.DataFrame(PCs, columns=['PC1', 'PC2'])
    loadings['feature'] = feature_names
    layout = pd.DataFrame(embeddings, columns=['posX', 'posY'])
    layout['entity'] = entities
    layout['timestamp'] = timestamps
    return layout, loadings

