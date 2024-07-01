import pandas as pd
import numpy as np
from datetime import datetime
from SpreadLine.utils import str_to_datetime, datetime_to_str, get_time_array
from SpreadLine.utils.constructors import find_within_constraints, construct_egocentric_network, filter_time_by_ego
from SpreadLine.order import ordering
from SpreadLine.align import aligning
from SpreadLine.compact import compacting
from SpreadLine.render import rendering
from SpreadLine.contextualize import contextualizing
from SpreadLine.utils import Node, Session, Entity, _check_validity

class SpreadLine():
    """Produce the rendered layout of SpreadLine.

    Parameters
    ----------
    _topo: pd.DataFrame
        The topology of the data. Should contain the following information: source, target, time, and edge weight.
    _node_color: pd.DataFrame
        The content of the data, to be used as the node color that helps conclude the relationship between a pair of nodes.
    _content: pd.DataFrame
        The content of the data, to be used as the attribute-driven layout that helps understand the contextual relationships among all the nodes. 

        The user can provide a predefined layout or the high-dimensional information that will be processed by dimensionality reduction methods. 
        
        The configurations are specified in `_content_config`. 
    _content_config: dict, values default True
        Specifies `_content` information. Whether a predefined layout is provided and whether the layout is dynamic. It contains only two keys, "dynamic" and "generated", where both store boolean values.
    time_format: str
        The format of the time in the data, which should be recognizable to datetime.
    ego: str|int
        The name of the ego in the data. This is specified by `ego` in `.center()` function.
    

    Attributes
    ----------
    _all_timestamps: list[str]
        All the time points within the time extents in the data, where the time granularity is specified by `timeDelta` in `.center()` function.
    locations: dict, values default empty list[int]
        The types of the sessions, "contact" or "idle". The constraints for the latter will be relaxed when generating the layout.

    entities: list[Entity]
        The unique entities in the data.
    entities_names: list[str]
        The names of `entities`
    sessions: list[Session]
        The interactions among nodes per time point, automatically derived from the data, depending on the ego.
    context: dict, values default empty pd.DataFrame
        Stores the attribute-driven layout and its loadings (for interpretation if needed) that will be rendered. Keys are "layout" and "loadings".

    
    Methods
    -------
    load:

    center:

    configure:

    """
    def __init__(self):
        self._topo: pd.DataFrame = None
        self._groups: dict = {} # How to construct groups of entities
        #TODO: make this more flexible
        # Content needs (1) entity node color that concludes the relations (2) entity line color (3) entity content layout
        # self._content = {"entity_category": , "entity_node":, "entity_content_layout": }

        self._node_color: pd.DataFrame = pd.DataFrame([], columns=['time', 'entity'])
        self._content: pd.DataFrame = None #  The layout of the block
        self._content_config: dict = { # Whether entity behavior changes over time or the layout is pre-defined by the user
            'dynamic': True,
            'generated': True,
        }
        self._line_color: dict = {}
        self.time_format: str = ''
        self._all_timestamps: list[str] = [] # Includes all of the dates given the date extents, consistent with the rendered time labels
        self.locations: dict = {
            'contact': [],
            'idle': [],
        }
        
        self.ego: str|int = None  # The name of the ego
        self.egoIdx: int = -1 # THe index of the ego in the entities_names
        self.entities: list[Entity] = []
        self.entities_names: list[str] = []
        self.sessions: list[Session] = [] # sessions with trade
        self.context: dict = None 


        self.effective_timestamps: list[int] = [] # excludes the dates with no changes, consistent with the table columns
        self._tables: dict = {}
        self.span: tuple = () # should be (numEntities, numTimestamps)
        self._counts: dict = {
            'numAllTimestamps': 0,  # the length of self._all_timestamps
            'numTimestamps': 0, # the length of self.effective_timestamps
            'numEntities': 0,
        }

        self._config: dict = {
            'bandStretch': [],
            'squeezeSameCategory': False,
            'minimize': 'space', # 'wiggles', 'space'
        }

        self._render = {}
    
    def getSessionByID(self, ID: int) -> Session:
        for each in self.sessions:
            if each.id == ID: return each
        return None
    
    def getEntityByName(self, name: str) -> Entity:
        for each in self.entities:
            if each.name == name: return each
        return None
    
    def load(self, filePath: str|pd.DataFrame, config: dict, key: str = 'topology', jsonOrient: str='split'):
        """Loads the file, any pd.DataFrame, *.csv, and *.json, into _raw as a pd.DataFrame with renamed columns.
        This is for the contents of the nodes, where the config should specify which column is the entitiy identifier and which column is the timestamp. 
        The rest of the columns would be all treated as multivariate information and being used in the attribute-driven layout. 

        Parameters
        ----------
        filePath: pd.dataFrame, or str that ends with ".csv" or ".json".
        config: dict. Keys are fixed (see examples) with their values being the column names/keys in the provided file.
        jsonOrient: str, optional. Only used when taking the json, this specifies the orient when reading into a pd.DataFrame.
        """
        # Reading in different types of files
        receipient = None
        if isinstance(filePath, pd.DataFrame): receipient = filePath
        elif isinstance(filePath, str): 
            fileExtension = filePath.split('.')[-1]
            if fileExtension == 'csv': receipient: pd.DataFrame = pd.read_csv(filePath)
            elif fileExtension == 'json': receipient: pd.DataFrame = pd.read_json(filePath, orient=jsonOrient)
        # Handling the loaded file differently based on the key
        if isinstance(receipient, pd.DataFrame) and key == 'topology':
            self._topo = _check_validity(receipient, config, rules = ["time", "source", "target", "weight"])
            return
        if isinstance(receipient, pd.DataFrame) and key == 'content':
            if not set(["timestamp", "id", "posX", "posY"]).issubset(set(config.keys())): raise KeyError("Unmatched keys in the config")
            if config['timestamp'] == "": # If the content layout is static
                self._content_config.update({'dynamic': False})
                config.pop('timestamp', None)
            if config['posX'] == "" and config['posY'] == "": # If the content layout is not pre-computed
                self._content_config.update({'generated': False})
                config.pop('posX', None)
                config.pop('posY', None)
            if not set(config.values()).issubset(set(receipient.columns)): raise ValueError("Unmatched values in the config")
            invConfig = {val: key for key, val in config.items()}
            receipient.rename(columns=invConfig, inplace=True)
            receipient.drop_duplicates(inplace=True)
            self._content = receipient
            return
        if isinstance(receipient, pd.DataFrame) and key == 'node':
            self._node_color = _check_validity(receipient, config, rules=['time', 'entity', 'context'])
            return
        if isinstance(receipient, pd.DataFrame) and key == 'line':
            receipient = _check_validity(receipient, config, rules=['entity', 'color'])
            receipient = receipient.loc[:, ['entity', 'color']].set_index('entity')
            self._line_color = receipient.squeeze(axis=0).to_dict()['color']
            return
        raise NotImplementedError("Not supported file types")

    def center(self, ego: str, timeExtents: list[str] = None, timeDelta: str = 'day', timeFormat: str = "%Y-%m-%d", groups: dict = {}):
        """Given the ego and the desired time range and granularity, construct the egocentric network from the data, aggregated if needed.

        Parameters
        ----------
        ego: str. The name of the ego.
        timeExtents: [str, str]. The time range of the egocentric network, whose format should be consistent with timeFormat.
            If not provided, then assume the entire network (_raw) should be considered.
        timeDelta: str. The time granularity.
        timeFormat: str. The format of the timestamps, should be consistent with _raw and timeExtents.
        """
        self.time_format: str = timeFormat
        self.ego: str = ego
        self._groups = groups
        #print(self._topo['time'].unique().tolist())
        self._topo['time'] = self._topo['time'].apply(lambda x: str_to_datetime(x, timeFormat))
        #print(self._topo['time'].unique().tolist())
        self._topo = filter_time_by_ego(ego, self._topo)
        if not timeExtents:
            timeExtents: list[str] = [datetime_to_str(self._topo['time'].min(), timeFormat), datetime_to_str(self._topo['time'].max(), timeFormat)]
        assert len(timeExtents) == 2, "timeExtents should only take a range of timestamps."
        #TODO: check if we really need str, or datetime is good enough
        #NOTE: this returns one more time point for the given time extents for the data aggregation to work as expected
        self._all_timestamps: list[str] = get_time_array(timeExtents, timeDelta, timeFormat)
        self._counts.update({'numAllTimestamps': len(self._all_timestamps)})
        timeArray: list[datetime] = [str_to_datetime(each, timeFormat) for each in self._all_timestamps]

        topo_within_time: pd.DataFrame = self._topo.loc[(self._topo['time'].between(timeExtents[0], timeExtents[1], inclusive="both")), :]

        network: pd.DataFrame = construct_egocentric_network(self.ego, topo_within_time)
        self._construct_entities(network)
        
        sessions: list[Session] = self._construct_contact_sessions(network, timeArray)
        self.locations.update({'contact': [each.id for each in sessions]})
        self._construct_timelines_idle_sessions(sessions)

        self._construct_tables()
        self.egoIdx = self.entities_names.index(self.ego)

    def configure(self, config: dict):
        if not set(config.keys()).issubset(set(self._config.keys())): raise KeyError("Unmatched keys in the config")
        self._config.update(config)

    # This is how we determine the hops
    def _construct_contact_sessions(self, network: pd.DataFrame, timeArray: list[datetime]):
        """ 
        Construct the sessions to be the Session object. One timestamp should only have one contact session.
        """
        sessionID: int = 0
        sessions: list[Session] = []
        names: list[str] = self.entities_names
        tIdx: int
        time: str
        for tIdx, time in enumerate(timeArray[:-1]):
            entries: pd.DataFrame = network.loc[(network['time'].between(time, timeArray[tIdx + 1], inclusive="left")), :]
            if entries.empty: continue
            sessionID += 1
            count: int = entries['weight'].sum()
            arcs: list[tuple] = entries.apply(lambda row: tuple(row[['source', 'target', 'weight']]), axis=1).tolist() 
            groups = self._groups.get(self._all_timestamps[tIdx], [])
            groups = [list(each) for each in groups]
            if len(groups) != 0:
                order = groups
                constraints = [groups[0], {1: groups[1]} if len(groups[1]) != 0 else {}, groups[2], {1: groups[3]} if len(groups[3]) != 0 else {}, groups[4]]
            #constraints = [{"1": group} if idx in [1,3] else group for idx, group in enumerate(groups)]
            #print(constraints)
            else:   
                constraints, order = find_within_constraints(entries, self.ego, self._line_color)
            #print(constraints)
            entities: list[str] = [each for hop in order for each in hop]
            entitiesIDs: list[int] = [names.index(each) for each in entities]     
            entities: list[Node] = [ Node(names[each], sessionID, order=idx, index=each) for idx, each in enumerate(entitiesIDs) ]
            indices: list[int] = entries.index.tolist()
            session = Session(sessionID, entities, form='contact', timestamp=tIdx, weight=count, indices=indices)
            session.set(hops=order, links=arcs, constraints=constraints)
            sessions.append(session)
        self.sessions = sessions
        return sessions

    def _construct_entities(self, network: pd.DataFrame):
        """ 
        Build the Entity structure for each entity in the egocentric dynamic network.
        """
        entities_names: list[str] = pd.concat([network['source'], network['target']]).unique().tolist()
        self.entities_names = entities_names
        entities = []
        #TODO: here we should also preprocess colors
        for rIdx, entity in enumerate(entities_names):
            timeline = np.full(self._counts['numAllTimestamps'], 0) 
            entitiy = Entity(name = entity, timeline = timeline, index = rIdx)
            entities.append(entitiy)
        self.entities = entities
        self._counts.update({'numEntities': len(entities)})

    def _construct_timelines_idle_sessions(self, sessions: list[dict]):
        """ 
        Based on the effective sessions, build each entity's timeline.
        Idle sessions are created to complete the timeline when the entity is not involved in that snapshot.
        """
        idleID = len(sessions) + 1
        idleLoc = set()
        session: Session
        for session in sessions:
            cIdx: int = session.timestamp
            sessionID: int = session.id
            node: Node
            names = session.print_entities()
            for node in session.entities:
                entity: Entity = self.getEntityByName(node.name)
                timeline = entity.timeline
                if np.all(timeline == 0): # initialize this information
                    timeline[cIdx] = sessionID
                    entity.timeline: np.ndarray = timeline # make sure timeline is updated
                    continue
                lastIdx = np.max(np.nonzero(timeline))
                #NOTE: now this can be the node if needed
                timeline[cIdx] = sessionID
                if cIdx - lastIdx > 1:
                    timeline[lastIdx+1:cIdx] = idleID
                    #NOTE: maybe ideally we want this, and then relax the constraints on the idle sessions
                    idleLoc.add(idleID)
                    idleID +=1  # this is each entity has its own idle session
        self.locations.update({'idle': idleLoc})
    
    def _construct_tables(self):
        """
        Based on the completed timelines, now initialize the table for the upcoming layout optimization.
        Snapshots where nothing changed would be merged.
        """
        timelines = []
        for entity in self.entities:
            timelines.append(entity.timeline)
        # rows are each entity, columns are each timestamp, cells are the session IDs
        timelines: np.ndarray = np.array(timelines)[:, :-1] # remove the day that was used for aggregation
                
        # Drop those columns(dates) where nothing changed
        _, unique_indices = np.unique(timelines, axis=1, return_index=True)
        unique_indices.sort()
        sessionTable = timelines[:, unique_indices]
        # update this to be consistent with the table for optimization
        for entity in self.entities:
            entity.timeline = sessionTable[entity.id, :]
        self.span = sessionTable.shape

        presenceTable = np.full(self.span, 0)
        idleSessions = self.locations['idle']
        for (rIdx, cIdx) in zip(np.nonzero(sessionTable)[0], np.nonzero(sessionTable)[1]):
            if sessionTable[rIdx, cIdx] in idleSessions: presenceTable[rIdx, cIdx] = -1
            else: presenceTable[rIdx, cIdx] = 1
        self.effective_timestamps = unique_indices
        self._tables.update({'session': sessionTable, 'presence': presenceTable})
        self._counts.update({'numTimestamps': len(self.effective_timestamps)})

    def fit(self, width:int = 1400, height:int = 500): # screen pixels
        """The pipeline to generate and render the layout with the given viewbox size

        Parameters
        ----------
        width: int. The desired width of the visualization in screen pixels.
        height: int. The desired height of the visualization in screen pixels.

        Returns
        -------
        render: dict. This stores the rendering information of all the visual elements as svg elements. 
        """
        # Step 1. Ordering the entities per timestamp, based on the given ordering the constraints, to minimize crossings in a sweeping manner.
        orderTable, orderedEntities, orderedIdleEntities, orderedSessions = ordering(self)
        self._tables.update({'order': orderTable})
        # Step 2. With the order fixed, align the entities in neighboring timestamps to maximize the number of straight lines.
        alignTable, sessionAlignTable = aligning(self, orderedEntities, orderedIdleEntities)
        self._tables.update({'align': alignTable})
        # Step 3. Under the ordering constraints and assigned alignments, compact the white spaces. (TODO: make sure this is accurate)
        heightTable, sideTable = compacting(self, orderedEntities, orderedSessions, sessionAlignTable)
        self._tables.update({'height': heightTable, 'crossing': sideTable})
        # Step 4. 
        context = contextualizing(self)
        self.context = context
        # Step 5. Render
        size = {'width': width, 'height': height}
        result = rendering(size, self)

        return result

    