import numpy as np
from SpreadLine.utils import Node, Session
from SpreadLine.utils.helpers import _sparse_argsort


def ordering(liner, iteration=10):
    """
    Perform ordering of sessions in SpreadLine liner. Each iteration consists of two steps: forward sweeping and backward sweeping. 
    The purpose of sweeping is to reduce the number of crossings between sessions across timestamps.

    Args:
        liner (SpreadLine): The SpreadLine liner object.
        iteration (int, optional): The number of iterations for the ordering algorithm. Defaults to 10.

    Returns:
        np.ndarray: The ordering results in the form of a numpy array.
    """
    sessionsPerTimestamp: list[list[Session]] = _bundle_entities_by_timestamp(liner)
    numTimestamps: int = liner._counts.get('numTimestamps')
    idleLocations: list[int] = liner.locations.get('idle')
    sessionTable: np.ndarray = liner._tables.get('session', {})

    for _ in range(0, iteration):
        # forward sweeping
        for cIdx in range(0, numTimestamps-1):
            currentSessions: list[Session] = sessionsPerTimestamp[cIdx]
            nextSessions: list[Session] = sessionsPerTimestamp[cIdx + 1]
            sessionsPerTimestamp[cIdx + 1] = _constrained_crossing_reduction(currentSessions, nextSessions)
        # backward sweeping
        for cIdx in range(numTimestamps-1, 0, -1):
            currentSessions: list[Session] = sessionsPerTimestamp[cIdx]
            prevSessions: list[Session] = sessionsPerTimestamp[cIdx - 1]
            sessionsPerTimestamp[cIdx - 1] = _constrained_crossing_reduction(currentSessions, prevSessions)
    # populate the ordering results in the orderTable
    orderTable = np.full(liner.span, 0)
    for cIdx in range(0, numTimestamps):
        sessions: list[Session] = sessionsPerTimestamp[cIdx]
        nodes: list[Node] = [each for session in sessions for each in session.entities]
        for node in nodes:
            rIdx = node.id
            orderTable[rIdx][cIdx] = node.order + 1 # given the default order starts from 0
    
    #NOTE: update the orderedEntities to be here
    orderedEntities = [] #NOTE: this is orderTable.T
    orderedIdleEntities = [] # this will be a subset of orderedEntities
    orderedSessions = []
    for cIdx in range(0, numTimestamps):
        orderedEntity: np.ndarray = _sparse_argsort(orderTable[:, cIdx]) # the indices of the entity, sorted by the order table
        orderedEntities.append(orderedEntity)

        orderedIdleEntity =[each for each in orderedEntity if sessionTable[each, cIdx] in idleLocations]
        orderedIdleEntities.append(orderedIdleEntity)

        sessionIDs = [sessionTable[each, cIdx] for each in orderedEntity]
        # This is the same as set() but it preserves the insertion order of the list
        orderedSession = list(dict.fromkeys(sessionIDs))
        orderedSessions.append(orderedSession)

    orderedEntities: np.ndarray = np.array(orderedEntities, dtype=object) # (numTimestamps, numSessionsPerTimestamp, numEntitiesPerSession)
    orderedIdleEntities: np.ndarray = np.array(orderedIdleEntities, dtype=object)
    orderedSessions = np.array(orderedSessions, dtype=object) # (numTimestamps, numSessionsPerTimestamps)

    return orderTable, orderedEntities, orderedIdleEntities, orderedSessions

def _bundle_entities_by_timestamp(liner) -> list[list[Session]]:
    """
    For each timestamp, create a nested list, where each element refers to a list of sessions at a timestamp.
    Given only idle sessions may exist across timestamps, dummy sessions are created here.

    Args:
    liner (SpreadLine): The SpreadLine liner object.

    Returns:
    A nested list of sessions, where each element refers to a session for a given timestamp.
    """
    sessionTable: np.ndarray = liner._tables.get('session', {})
    numTimestamps: int = liner._counts.get('numTimestamps')
    sessionsPerTimestamp: list[list[Session]] = []
    idleLocations: list[int] = liner.locations.get('idle')
    names: list[str] = liner.entities_names
    for cIdx in range(0, numTimestamps):
        sessions: list[Session] = []
        for sessionID in np.unique(sessionTable[:, cIdx]):
            if(sessionID == 0): continue
            if sessionID not in idleLocations:
                session: Session = liner.getSessionByID(sessionID)
            else: # idle session, create Session objects for idle sessions per timestamp on demand
                entitiesIDs: list[int] = np.argwhere(sessionTable[:, cIdx] == sessionID).flatten().tolist()
                entitiesIDs = np.sort(entitiesIDs, axis=0)
                entities = [Node(names[each], sessionID, order=idx, index=each) for idx, each in enumerate(entitiesIDs)]
                session: Session = Session(sessionID, entities, form='idle')
            sessions.append(session)
        sessionsPerTimestamp.append(sessions)
    return sessionsPerTimestamp

def _constrained_crossing_reduction(currentSessions: list[Session], nextSessions: list[Session]) -> Session:
    currNodes: list[Node] = [each for session in currentSessions for each in session.entities]
    result = []
    session: Session
    for session in nextSessions:
        constraints: list[tuple] = session.constraints
        if len(constraints) == 0:
            result.append(session)
            continue
        topTwoHops, sourceGroup, _, targetGroup, bottomTwoHops = session.constraints
        # If the group only has one element then we don't need to sort it
        sweepRange = (0, len(topTwoHops))
        if len(topTwoHops) > 1: _within_sort(topTwoHops, session, currNodes, sweepRange)
        for weight, group in sourceGroup.items():
            sweepRange = (sweepRange[1], sweepRange[1] + len(group))
            if len(group) > 1: _within_sort(group, session, currNodes, sweepRange)
        
        sweepRange = (sweepRange[1], sweepRange[1] + 1) #ego

        for weight, group in targetGroup.items():
            sweepRange = (sweepRange[1], sweepRange[1] + len(group))
            if len(group) > 1: _within_sort(group, session, currNodes, sweepRange)
        #if len(targetGroup) > 1: _within_sort(targetGroup, session, currNodes, sweepRange)
        sweepRange = (sweepRange[1], sweepRange[1] + len(bottomTwoHops))
        if len(bottomTwoHops) > 1: _within_sort(bottomTwoHops, session, currNodes, sweepRange)
        #print(session.print_entities(), 'after')
        result.append(session)  
    return _barycenter_sort(currNodes, nextSessions)


def _within_sort(group: list[str], session: Session, currNodes: list[Node], sweepRange: tuple):
    nodes = [session.findNode(each) for each in group]
    nodes.sort(key=lambda x: x.getBarycenterLeaf(currNodes))
    session.replaceNode(nodes, sweepRange)

# Barycenter sort example: https://github.com/Hoderu/arc-diagrams-barycenter
#IMPORTANT! this is sorting different sessions
def _barycenter_sort(currNodes: list[Node], nextSessions: list[Session]) -> Session:
    """
    Ordering the sessions at the next/prev timestamp, whose barycenter is determined by the current timestamp.
    The barycenter is the sum of their order. Ideally, those with more existing elements at the current timestamps are not likely moved.
    """
    session: Session
    for session in nextSessions:
        # For those in the same session, find out how many exists in the previous session
        existed = [node.findSelf(currNodes) for node in session.entities]
        # how many relative order persists?
        barycenter = sum([each.order for each in list(filter(None, existed))])
        # higer number means preference of not moving?
        session.barycenter = barycenter / session.entityWeight
    nextSessions.sort(key=lambda x: x.barycenter)
    nodes: list[Node] = [each for session in nextSessions for each in session.entities]
    for session in nextSessions:
        for node in session.entities:
            node.order = nodes.index(node)
    return nextSessions
    



