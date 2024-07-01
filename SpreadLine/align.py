import numpy as np
from SpreadLine.utils import Session
from SpreadLine.utils.helpers import _sparse_argsort
import math

ALPHA = 0.1
# MINIMIZE the wiggle lines in the layout
def aligning(liner, orderedEntities, orderedIdleEntities):
    (numEntities, numTimestamps) = liner.span
    # rewards those who can lead to most straight lines through alignment
    rewards = _compute_rewards(liner, orderedEntities, orderedIdleEntities)

    #IMPORTANT!: up to here the crossing did not happen
    alignTable = np.full(liner.span, -1)
    for cIdx in range(0, numTimestamps - 1):
        alignment = longest_common_substring(len(orderedEntities[cIdx]), len(orderedEntities[cIdx + 1]), rewards[cIdx])
        for (currEnt, nextEnt) in alignment.items(): #key, value being alignId
            #alignTable[currEnt, cIdx] = nextEnt
            #NOTE: this would be retrieving correct entities
            #if orderedEntities[cIdx][currEnt] == liner.egoIdx:
            #    print('ego to', orderedEntities[cIdx+1][nextEnt])
            #NOTE: saw ego is always to ego here, so maybe something wrong with compacting
            #if names[orderedEntities[cIdx][currEnt]] != names[orderedEntities[cIdx+1][nextEnt]]:
            #print(names[orderedEntities[cIdx][currEnt]], names[orderedEntities[cIdx+1][nextEnt]], cIdx)
            alignTable[orderedEntities[cIdx][currEnt], cIdx] = orderedEntities[cIdx+1][nextEnt]
    
    sessionAlignTable = _align_sessions(liner, alignTable, orderedEntities)
    
    return alignTable, sessionAlignTable

def _align_sessions(liner, alignTable: np.ndarray, orderedEntities: np.ndarray) -> list[dict]:
    """
    Aligns the sessions based on the alignment table, which aligns individual entities.
    """
    sessionTable = liner._tables.get('session')
    ego: int = liner.egoIdx
    (numEntities, numTimestamps) = liner.span
    sessionAlignTable = []
    for cIdx in range(0, numTimestamps - 1):
        aligned: dict = {}
        orderedEnts: list[int] = orderedEntities[cIdx]
        #NOTE: ego must be all aligned to itself here
        if ego in orderedEnts: 
            sessionID: int = sessionTable[ego, cIdx]
            alignedSessionID: int = sessionTable[ego, cIdx + 1]
            aligned[sessionID] = alignedSessionID # These sessions are aligned
        for cha in orderedEnts:
            if cha == ego: continue
            sessionID = sessionTable[cha, cIdx]
            alignedEntity = alignTable[cha, cIdx]
            alignedSessionID = -1
            if (alignedEntity != -1):# it is aligned to someone
                alignedSessionID = sessionTable[alignedEntity, cIdx + 1] # 0 means invalid session
                if alignedSessionID == 0: alignedSessionID = -1
            # If thie session has not been aligned to any other session at this timestamp
            #TODO: check if this happens: session is not aligned yet, but alignedSessionID is already in aligned.values(), i.e., two sesstions want to be aligned with the same session.
            if aligned.get(sessionID, -1) == -1 and alignedSessionID in aligned.values():
                # If the to-be-aligned session is not taken yet
                #if alignedSessionID in aligned.values(): alignedSessionID = -1
                aligned[sessionID] = alignedSessionID
        sessionAlignTable.append(aligned)
    return sessionAlignTable

# compute sim(l_i, r_j), the similarity between sessions
def _compute_rewards(liner, orderedEntities, orderedIdleEntities):
    """
    Given two entities at two consecutive timestamps, we align the pair with the highest reward.
    The reward is the possible maximum number of straight lines plus the similarity of their relative orders.
    We enforce the ego should maintain the straight line so reward[ego, ego] should be the highest among reward[ego, :].
    """
    (_, numTimestamps) = liner.span
    rewards: list[list[list[int]]] = [] # 3D array, (numTimestamps, numSessionsPerTimestamp, numEntitiesPerSession)
    ego = liner.egoIdx
    names = liner.entities_names
    for cIdx in range(0, numTimestamps-1):
        currentReward: list[list[int]] = [] # (numCurrentEntities, numNextEntities)
        currentEntities: list[int] = orderedEntities[cIdx] # the indices of the entities
        nextEntities: list[int] = orderedEntities[cIdx + 1]
        #print([names[each] for each in currentEntities], [names[each] for each in nextEntities], 'yo')
        
        for currOrder, currEnt in enumerate(currentEntities):
            currEntReward: list[int] = []
            for nextOrder, nextEnt in enumerate(nextEntities):
                #NOTE: where bend or align constraints happen, line 53
                reward = 0
                currSessionEntIds: list[int] = _get_entities_in_session(currEnt, cIdx, liner, orderedIdleEntities[cIdx])
                nextSessionEntIds: list[int] = _get_entities_in_session(nextEnt, cIdx+1, liner, orderedIdleEntities[cIdx + 1])
                # straight(l_i, r_j), the maximum number of staight lines we can get from these two sessions
                #if cIdx == 4:
                #    print('yo', currSessionEntIds, nextSessionEntIds, np.in1d(currSessionEntIds, nextSessionEntIds))
                num_straight_lines = np.in1d(currSessionEntIds, nextSessionEntIds).sum()
                reward += num_straight_lines
                # similarity of the relative order
                compatibility = ALPHA * (1 - np.abs(
                    ((currOrder + 1) / len(currSessionEntIds)) -  # + 1 because starts at 0
                    ((nextOrder + 1) / len(nextSessionEntIds))
                ))
                reward += compatibility
                #If we are comparing ego across tiemstamps, then we want ensure the straight line by maximizing this reward
                if currEnt == ego and nextEnt == ego: reward = math.inf
                currEntReward.append(reward)
            currentReward.append(currEntReward)
        rewards.append(np.array(currentReward))
    rewards = np.array(rewards, dtype=object)
    return rewards

def _get_entities_in_session(rIdx:int, cIdx:int, liner, orderedIdleEntities) -> list[int]:
    """
    Get the list of entities in the session where the given entity is in.
    """
    #get the sessionID given the chararcter id and the timestamp
    sessionID = liner.entities[rIdx].getAtTimestamp(cIdx)
    idleLoc = liner.locations.get('idle')
    sessionTable = liner._tables.get('session')
    # get the Session instance given the id
    #NOTE: this only gives the tradeSession
    session: Session = liner.getSessionByID(sessionID)
    # return the indices of the entities of a session at given timestamp
    if sessionID in idleLoc:
        #entities = np.argwhere(sessionTable[:, cIdx] == sessionID).flatten().tolist()
        return orderedIdleEntities
    #print('contact', rIdx, cIdx, session.getEntityIDs(), sessionID)
    return session.getEntityIDs()

# find maximum sum of the matched pairs between entities
def longest_common_substring(currLength: int, nextLength: int, reward: dict) -> dict:
    """
    Finds the longest common substring between two sequences using dynamic programming.

    Args:
        currLength (int): The length of the current sequence.
        nextLength (int): The length of the next sequence.
        reward (dict): A dictionary representing the reward matrix for aligning elements.

    Returns:
        dict: A dictionary representing the alignment table, where the keys are indices of the current sequence
              and the values are the corresponding indices of the next sequence.

    """
    matchTable = {} # default is 0
    # Initialization
    for i in range(0, currLength):
        matchTable[i] = {}
        for j in range(0, nextLength):
            matchTable[i][j] = 0
    # memoization
    direction = {}
    for i in range(0, currLength):
        direction[i] = {}
        for j in range(0, nextLength):
            candidates = [
                matchTable.get(i-1, {}).get(j-1, 0) + reward[i, j], # i and j should be aligned
                matchTable.get(i, {}).get(j-1, 0), # i should not align with j, so maybe try j - 1, i.e., left goes up
                matchTable.get(i-1, {}).get(j, 0)  # j should not align with i, so maybe try i - 1, i.e., right goes up
            ]
            maxValue = max(candidates)
            maxIdx = candidates.index(maxValue)
            matchTable[i][j] = maxValue
            direction[i][j] = maxIdx

    alignTable: dict = {}
    currPtr: int = currLength - 1
    nextPtr: int = nextLength - 1
    while (currPtr >= 0 and nextPtr >= 0):
        if (direction[currPtr][nextPtr] == 0): # aligned
            alignTable[currPtr] = nextPtr
            currPtr -= 1
            nextPtr -= 1
        elif (direction[currPtr][nextPtr] == 1):
            nextPtr -= 1 # this entity in nextTime is not aligning with anyone
        elif (direction[currPtr][nextPtr] == 2):
            currPtr -= 1 # this entity in currentTime is not aligning with anyone
        else:
            break
    return alignTable


