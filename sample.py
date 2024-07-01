import pandas as pd
from SpreadLine.spreadline import SpreadLine

def create_entities(name, cat, color):
    return {'entity': name, 'category': cat, 'color': color}

entities = [
    create_entities('Ego', 'orange', '#E98B2A'),
    create_entities('A', 'orange', '#E98B2A'),
    create_entities('B', 'blue', '#507AA6'),
    create_entities('C', 'blue', '#507AA6'),
    create_entities('D', 'blue', '#507AA6'),
    create_entities('E', 'orange', '#E98B2A'),
]

def create_relations(source, target, quantity, time):
    return {'source': source, 'target': target, 'quantity': quantity, 'time': str(time)}

relations = [
    create_relations('C', 'A', 10, 2022),
    create_relations('A', 'Ego', 10, 2022),
    create_relations('Ego', 'B', 10, 2022),
    create_relations('B', 'D', 10, 2022),
    create_relations('B', 'E', 10, 2022),
    create_relations('D', 'E', 10, 2022),
    create_relations('D', 'Ego', 10, 2023),
    create_relations('A', 'Ego', 5, 2023),
    create_relations('Ego', 'B', 10, 2023),
    create_relations('B', 'D', 10, 2023),
    create_relations('B', 'E', 5, 2023),
]

SpreadLiner = SpreadLine()
ego = "Ego"
network = pd.DataFrame(relations)
lineColor = pd.DataFrame(entities)

SpreadLiner.load(network, config={
    'source': 'source',
    'target': 'target',
    'time': 'time',
    'weight': 'quantity',
}) 
SpreadLiner.load(lineColor, config={
    'entity': 'entity',
    'color': 'color'
}, key='line')
SpreadLiner.center(ego=ego, timeDelta='year', timeFormat='%Y')

result = SpreadLiner.fit(width=400, height=400)

print(result)
