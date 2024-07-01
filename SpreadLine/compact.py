import sys
import numpy as np
from SpreadLine.utils import Session, _sparse_argsort
from itertools import groupby
from operator import itemgetter
import itertools
import bisect


np.set_printoptions(threshold=sys.maxsize)
#TODO: daniel keim, still have hop issues

DISTANCE_LINE = 5 #10 # between lines
DISTANCE_HOP = 10#12
DISTANCE_SESSION = 5 # between sessions, this controls the distance between the ego sessions and the idle sessions
SQUEEZE_LINE = 5 #4 # between lines when they belong to the same category

THROUGH = False

def compacting(liner, orderedEntities, orderedSessions, sessionAlignTable):
    focus = liner._config.get('minimize')
    slots, slotsInEntities, egoSlotIdx = _construct_slots(liner, orderedEntities, orderedSessions, sessionAlignTable)
    if focus == 'space':
        heightTable = _compute_session_height_space(liner, slots, slotsInEntities, egoSlotIdx, through=THROUGH)
    else:
        heightTable = _compute_session_height_line(liner, slots, slotsInEntities, egoSlotIdx, through=THROUGH)
    sideTable = build_side_table(liner, heightTable)

    minOffset = np.abs(np.nanmin(heightTable))
    heightTable = heightTable + minOffset
    heightTable[np.isnan(heightTable)] = -1

    egoUniqueHeight = np.unique(heightTable[liner.egoIdx, :])
    assert len(egoUniqueHeight) == 1, 'Ego should only have one height'

    return heightTable, sideTable

def build_side_table(liner, heightTable):
    span = liner.span
    names = liner.entities_names
    (numEntities, numTimestamps) = span
    sideTable = np.full((numEntities, 1), 0, dtype=int)
    for rIdx in range(0, numEntities):
        mask = (~np.isnan(heightTable[rIdx, :]))
        #if names[rIdx] == 'Matthew Brehmer': print(heightTable[rIdx, mask])
        timeline = np.unique([np.sign(each) for each in heightTable[rIdx, mask]])
        if len(timeline) == 2: sideTable[rIdx] = 1
    return sideTable


def _construct_slots(liner, orderedEntities: np.ndarray, orderedSessions: list[list[int]], sessionAlignTable: list[dict]) -> tuple([np.ndarray, np.ndarray, int]):
    """
    Construct the slots, for the sessions, to be rendered, while compressing the white space. Note that one cell only contains one session.
    It starts with the first timestamp, where we assign each session into each slot.
    In each incremental timestamp, we first assign the ego, and then those that are meant to be aligned with others.
    Then, for those above(below) the ego that are not assigned, we find if there are available spaces to place them, going up(down) from the ego.
    If there are remaining unslotted sessions but the slots are full, we create a new slot and insert it while corresponding to the order. 
    Once this is done, we rearrage the slots of idle sessions to compress vertical white spaces.
    We then construct the ordered entities that follows the format of the slots.

    Parameters:
    - liner: The liner object that contains the necessary data for slot construction.
    - orderedEntities: An ndarray representing the ordered entities.
    - orderedSessions: A list of lists representing the ordered sessions for each timestamp.
    - sessionAlignTable: A list of dictionaries representing the alignment of sessions for each timestamp.

    Returns:
    A tuple containing the following:
    - An ndarray representing the constructed slots.
    - An ndarray representing the ordered entities.
    - An integer representing the index of the ego in the slots.
    """
    
    sessionTable = liner._tables.get('session')
    (numEntities, numTimestamps) = liner.span
    ego: int = liner.egoIdx
    egoSessions = sessionTable[ego, :]

    # Initialization and records the slotIdx where the ego is at.
    slots: list[list[int]] = [[each for each in orderedSessions[0]]]
    egoSlotIdx = list(orderedSessions[0]).index(egoSessions[0]) 
    
    for cIdx in range(1, numTimestamps):
        dealt = set()
        # Ensures the ego's session always go into the same slot.
        egoSessionID: int = egoSessions[cIdx]
        slots[egoSlotIdx].append(egoSessionID)
        dealt.add(egoSessionID)

        # Investigate who else need to be placed above/below the ego and their alignments
        sessions: list[int] = orderedSessions[cIdx]
        alignment: dict = sessionAlignTable[cIdx - 1]
        egoSessionOrder: int = list(sessions).index(egoSessionID)
        
        # Now iterate through existing slots to find who else should be inserted due to alignment, besides the ego and those are assigned to align with the ego
        for rIdx, slot in enumerate(slots):
            if rIdx == egoSlotIdx: continue
            prevSessionID = slot[cIdx - 1]
            insertSessionID = alignment.get(prevSessionID, -1)
            #NOTE: not sure if this is ever triggered
            if insertSessionID == egoSessionID: insertSessionID = -1 # ensures that all egoSessions are aligned in one slot
            slot.append(insertSessionID)
            if insertSessionID != -1: dealt.add(insertSessionID)
        
        # For those not aligned with anyone, we divide them into those who should be above the ego and those below the ego.
        unassigned = set(sessions) - dealt
        aboveSessions = list(filter(lambda x: (x in unassigned), sessions[:egoSessionOrder]))
        belowSessions = list(filter(lambda x: (x in unassigned), sessions[egoSessionOrder+1:]))
        #print(aboveSessions, belowSessions)

        #NOTE: this is problematic when we don't bundle idle sessions. See goodnotes p.33.
        #NOTE: but this currently seems fine, if anything is wrong, then line 97-99 and 108-110 would scream
        watcher = []
        for session in aboveSessions[::-1]: # start from the one that's closest to the ego
            for slotIdx in range(egoSlotIdx-1, -1, -1): # starts from egoSlotIdx-1, stops at 0
                if (slots[slotIdx][cIdx] != -1) or (session not in unassigned): continue
                # we only consider this when the slots are open and it is not assigned yet
                slots[slotIdx][cIdx] = session
                unassigned.remove(session)
                watcher.append(session)
        order = "#".join([str(each[cIdx]) for each in slots])
        curr = '#'.join([str(each) for each in watcher[::-1]])
        if curr not in order: print(curr, order, 'above')

        watcher = []
        for session in belowSessions: # same but from different range
            for idx in range(egoSlotIdx+1, len(slots)):
                if (slots[idx][cIdx] != -1) or (session not in unassigned): continue
                slots[idx][cIdx] = session
                unassigned.remove(session)
                watcher.append(session)
        order = "#".join([str(each[cIdx]) for each in slots])
        curr = '#'.join([str(each) for each in watcher])
        if curr not in order: print(curr, order, 'below')

        
        # If the existing slots are full, then we have to add new slots
        unassigned = list(unassigned)
        unassigned.sort(key=lambda x: sessions.index(x))
        for session in unassigned:
            currentSpots: list[int] = [each[cIdx] for each in slots]
            order: int = sessions.index(session) # Find out its order in this timestamp
            # Prepare the new slot
            newSlot: list[int] = [-1]*cIdx
            newSlot.append(session)
            if order == 0: # If it is meant to be placed above anyone
                slots.insert(0, newSlot)
                egoSlotIdx += 1
            elif order == len(sessions)-1: # If it is to be placed below anyone
                slots.append(newSlot)
            else: # If it is between existing slots
                prevIdx = currentSpots.index(sessions[order-1]) # Find out where is the one that supposed to be above it
                slots.insert(prevIdx+1, newSlot)
                if prevIdx < egoSlotIdx: egoSlotIdx += 1
    slots = np.array(slots)
    
    slotsInEntities = np.full(slots.shape, -1, dtype=object) # (numSlots, numTimestamps, numEntitiesPerSession)
    for cIdx in range(0, numTimestamps):
        for rIdx in range(0, slots.shape[0]):
            if slots[rIdx, cIdx] == -1: continue
            session: int = slots[rIdx, cIdx]
            entities: np.ndarray = orderedEntities[cIdx]
            sessionEntities: list[int] = [each for each in entities if sessionTable[each, cIdx] == session]
            slotsInEntities[rIdx, cIdx] = np.array(sessionEntities)
            continue
    return slots, slotsInEntities, egoSlotIdx

def _get_groups(nums, size=3):
    groups = []
    currVal = nums[0]
    leftPtr = 0
    rightPtr = 0
    for idx, num in enumerate(nums):
        if idx == 0: continue
        rightPtr = idx
        if num != currVal:
            if (rightPtr - leftPtr) + 1 >= size:
                groups.append([leftPtr, rightPtr])
            currVal = num
            leftPtr = idx
    if (rightPtr - leftPtr) + 1 >= size:
        groups.append([leftPtr, rightPtr+1])
    return groups

def _are_on_same_side(oneSide: str|int|float, otherSide: str|int|float):
    if isinstance(oneSide, str) and isinstance(otherSide, str): return oneSide == otherSide
    elif not isinstance(oneSide, str) and not isinstance(otherSide, str): return np.sign(oneSide) == np.sign(otherSide)
    elif isinstance(oneSide, str) and not isinstance(otherSide, str):
        temp = oneSide
        oneSide = otherSide
        otherSide = temp
    # oneSide is a number and otherSide is a string
    sign = np.sign(oneSide)
    if sign == 1 and otherSide == 'below': return True
    if sign == -1 and otherSide == 'above': return True
    return False

#TODO: fix idle here
def _compute_idle_session_height(liner, heightTable: np.ndarray, slots: np.ndarray, slotsInEntities: np.ndarray, egoSlotIdx: int, blockRange: np.ndarray, through: bool):
    span = liner.span
    names = liner.entities_names
    (numEntities, numTimestamps) = span
    colors = liner._line_color
    categories = np.unique(list(colors.values()))
    bundleDict = {}

    # This aligns the non-ego, i.e., idle sessions
    def _is_available(number, cIdx, heights):
        throughFlag = (blockRange[0, cIdx] < number < blockRange[1, cIdx]) if through is True else False
        notConflict = (blockRange[0, cIdx] > number) | (number > blockRange[1, cIdx])
        #if through: notConflict = True
        if blockRange[0, cIdx] == blockRange[1, cIdx]: throughFlag = True
        return (throughFlag | notConflict) & (number not in heights)
    
    def _is_not_conflict(number, cIdx, rIdx):
        otherHeights = np.unique(heightTable[:rIdx, cIdx]).tolist() + np.unique(heightTable[rIdx+1:, cIdx]).tolist()
        notConflict = (blockRange[0, cIdx] > number) | (number > blockRange[1, cIdx])
        if through == True: notConflict = True
        return notConflict & (number not in otherHeights)
        #return notConflict & (number not in heightTable[:, cIdx])
    
    assign = {}
    idleAssign = {}
    unchecked = {}
    # This enforces them to stay on the same side if the identity does not change
    for cIdx in range(0, numTimestamps):
        sessions = slots[:, cIdx]
        heights = heightTable[:, cIdx]#.copy() 
        for slotIdx, session in enumerate(sessions): # from top to down
            if session == -1 or session == slots[egoSlotIdx, cIdx]: continue
            entities = slotsInEntities[slotIdx, cIdx]
            direction = 'above' if slotIdx < egoSlotIdx else 'below'

            assert len(entities) == 1, "An idle session is supposed to only have one entity"
            rIdx = entities[0]
            if assign.get(rIdx, None) is None: assign[rIdx] = {}
            if idleAssign.get(cIdx, None) is None: idleAssign[cIdx] = {}
            if unchecked.get(rIdx, None) is None: unchecked[rIdx] = {}
        
            leftCIdx = cIdx - 1 - (~np.isnan(heightTable[rIdx, :cIdx]))[::-1].argmax() 
            rightCIdx = (~np.isnan(heightTable[rIdx, cIdx+1:])).argmax() + cIdx + 1
            leftSide = heightTable[rIdx, leftCIdx]
            rightSide = heightTable[rIdx, rightCIdx]
            sameSide = _are_on_same_side(leftSide, rightSide)

            idles = [each for each in range(leftCIdx+1, rightCIdx)]
            if all([unchecked[rIdx].get(cIdx, True)for cIdx in idles]): #never recorded before
                idleAssign[cIdx][rIdx] = np.array(idles)
                for each in idles: unchecked[rIdx][each] = False

            assignment = -1
            abovePos = blockRange[0, cIdx]
            belowPos = blockRange[1, cIdx]
            while abovePos in heights: abovePos = abovePos - DISTANCE_SESSION
            while belowPos in heights: belowPos = belowPos + DISTANCE_SESSION
            #abovePos = np.nanmin(heights) - DISTANCE_SESSION
            #belowPos = np.nanmax(heights) + DISTANCE_SESSION
            #print(names[rIdx], cIdx, sameSide, direction)

            if not sameSide: # then we follow the arrangement by the slots
                #print('here')
                assignment = abovePos if direction == 'above' else belowPos
                if _are_on_same_side(assignment, leftSide) and _is_available(leftSide, cIdx, heights): assignment = leftSide
                if _are_on_same_side(assignment, rightSide) and _is_available(rightSide, cIdx, heights): assignment = rightSide
            # Same side and same assignment (above)
            elif _are_on_same_side(leftSide, direction): 
                assignment = abovePos if direction == 'above' else belowPos
                #print('there', _are_on_same_side(assignment, leftSide), _is_available(leftSide, cIdx, heights))
                if _are_on_same_side(assignment, leftSide) and _is_available(leftSide, cIdx, heights): assignment = leftSide
                if _are_on_same_side(assignment, rightSide) and _is_available(rightSide, cIdx, heights): assignment = rightSide
            else:  # same side, but assignment is different
                #print('bleh')
                assignment = abovePos if np.sign(leftSide) == -1 else belowPos

            #print(assignment, abovePos, belowPos, leftSide, rightSide)
            heights[rIdx] = assignment
            assign[rIdx][cIdx] = assignment

    for rIdx, assignment in assign.items():
        for cIdx, height in assignment.items():
            heightTable[rIdx][cIdx] = height

    def _stretch_to_reduce_wiggles(rIdx: int, heights: np.array, timestamps: np.array, direction: str):
        assignment = np.nanmin(heights) if direction == 'above' else np.nanmax(heights)
        order = np.sort(np.unique(heights))
        if direction == 'above': order = order[::-1]
        for candidate in order: # try to find a height that works for every timestamp, i.e., a straight line
            if all([_is_not_conflict(candidate, cIdx, rIdx) for cIdx in timestamps]):
                assignment = candidate
                heightTable[rIdx, timestamps] = assignment
                return
        while all([_is_not_conflict(assignment, cIdx, rIdx) for cIdx in timestamps]) == False:
            assignment -= DISTANCE_SESSION if direction == 'above' else (-1)*DISTANCE_SESSION
        heightTable[rIdx, timestamps] = assignment
        

    for cIdx, entities in idleAssign.items():
        for rIdx, indices in entities.items():
            heights = heightTable[rIdx, indices] # consecutive
            positions = np.sign(heights)
            above = (positions == -1)
            below = (positions == 1)
            if any(above) and sum(above) > 1: _stretch_to_reduce_wiggles(rIdx, heights[above], indices[above], 'above')
            if any(below) and sum(below) > 1: _stretch_to_reduce_wiggles(rIdx, heights[below], indices[below], 'below')
            
    return heightTable

def _find_same_range(nums, idx, heights: list[int], sameSide=False):
    value = nums[idx]
    start = idx
    while start > 0 and nums[start - 1] == value: 
        if sameSide and (_are_on_same_side(heights[idx], heights[start-1]) == False): break
        start -= 1
    end = idx
    while end < len(nums) - 1 and nums[end + 1] == value: 
        if sameSide and (_are_on_same_side(heights[idx], heights[end+1]) == False): break
        end += 1
    return [start, end+1]

def _compute_session_height_line(liner, slots: np.ndarray, slotsInEntities: np.ndarray, egoSlotIdx: int, through=True):
    span = liner.span
    (numEntities, numTimestamps) = span
    heightTable = np.full(span, np.nan)
    ego = liner.egoIdx
    names = liner.entities_names
    colors = liner._line_color
    presenceTable = liner._tables.get('presence')
    effectiveTimestamps = liner.effective_timestamps
    allTimestamps = liner._all_timestamps
    if liner._config.get('squeezeSameCategory'): SQUEEZE_LINE = 2#2.25

    # Initialization, affirmed to be correct
    block = {}
    sessions = {}
    assign = {}
    DEBUG = False
    for cIdx in range(0, numTimestamps):
        entities: np.ndarray = slotsInEntities[egoSlotIdx, cIdx]
        sessionID: int = slots[egoSlotIdx, cIdx]
        session: Session = liner.getSessionByID(sessionID)
        egoIdx = entities.tolist().index(ego)
        # Initialize the within distance among entities at each timestamp
        heights = [0]
        for idx, rIdx in enumerate(entities):
            if idx == 0: continue
            distance: int = _determine_distance(liner, rIdx, entities[idx-1], session)
            heights.append((heights[-1] + distance))
        heights = np.array(heights)
        heights -= heights[egoIdx]
        for rIdx in (entities[:egoIdx][::-1].tolist() + entities[egoIdx+1:].tolist()):
            if assign.get(rIdx, None) is None: assign[rIdx] = []
            assign[rIdx].append(cIdx)
        block[cIdx] = entities
        sessions[cIdx] = sessionID
        heightTable[entities, cIdx] = heights

    referenceTable = np.copy(heightTable)
    dealt = {}
    idleDealt = {}
    def _should_update(rIdx: int, assign: int, currHeights: list[int], reference: list[int], restEntities: list[int], direction=1):
        result: list[bool] = []
        differences: list[int] = []
        #print(assign, [names[each] for each in restEntities], [currHeights[each] for each in restEntities])
        for entity in restEntities:
            #print(names[entity])
            desiredDifference: int = (reference[entity] - reference[rIdx]) * direction
            # If we assign it, what would be the difference
            currDifference: int = (currHeights[entity] - assign) * direction
            difference: int = desiredDifference
            if DEBUG and names[rIdx] == 'Daniel A. Keim': 
                print(assign, currHeights[entity], desiredDifference, currDifference, differences, names[entity])
            # Maybe this needs to look at the currDifference
            if np.isnan(desiredDifference): # that means entity was idle, //TODO: decide more here, is it part of result?
                #print('idle session appears when assigning an non-idle session', names[entity], currHeights[entity], currDifference)
                # Either the assignment will take the same spot, or others to be moved will do. In that case, we canont allow this
                assumedDifference = _determine_distance(liner, rIdx, entity, None, idle=True)
                withinDifferences = [(abs(each - currDifference) < assumedDifference) for each in differences if np.isnan(each) == False]
                if DEBUG and names[rIdx] == 'Daniel A. Keim': print(currDifference, differences, withinDifferences, any(withinDifferences), 'yoooo')
                if ((currHeights[entity] == assign) or any(withinDifferences)) and dealt.get(entity, False): result.append(False)
                differences.append(difference) # should not be mobed
                continue

            assumedDifference = _determine_distance(liner, rIdx, entity, None, idle=True)
            withinDifferences = [(abs(each - currDifference) < 1.75) for each in differences if np.isnan(each) == False]
            if DEBUG and names[rIdx] == 'Daniel A. Keim': print(currDifference, desiredDifference, withinDifferences, all(withinDifferences), 'seal')
            unaffected: bool = (currDifference > desiredDifference)
            # If it the currDifference is too small and then we haven't dealt with entity yet, then we are safe to move the entity
            shouldBeMoved: bool = (currDifference < desiredDifference) & (dealt.get(entity, False) == False)
            #print(currDifference, desiredDifference, dealt.get(entity, False), names[entity])
            if unaffected and (not any(withinDifferences)): difference = currDifference # This means assignment does not affect this entity, so we leave it be
            if unaffected and (any(withinDifferences)): 
                candidates = np.array([each for each in differences if np.isnan(each) == False])[withinDifferences]
                difference = np.max(candidates) + 1.75
                #print(candidates, 'candidates')
            differences.append(difference) 
            result.append((unaffected|shouldBeMoved)) # Otherwise we have to move others
        # All the non-idle entities have to be either unaffected or moved, then we will update this assignment
        if DEBUG and names[rIdx] == 'Daniel A. Keim': print(result, differences, 'yoooo')
        return all(result), differences

    def _assign_nonidle_entity(rIdx: int, cIdx: int, assign: int, curr: int, reference: np.ndarray, restEntities: list[int], direction=1):
        result: list[int] = []
        resultEntities: list[int] = []
        # If our assignment wants to move it up when it is below, or move it down when it is above, then it is unavailable
        # NOTE: this should avoid 2-hops being above/below some 1-hop, causing some rendering errors.
        unavailable: bool = (assign < curr)  if direction == 1 else (assign > curr)
        if DEBUG and names[rIdx] == 'Daniel A. Keim': print(assign, curr, [names[each] for each in restEntities], [reference[each] for each in restEntities], unavailable)
        if unavailable: 
            return resultEntities, result
        # Handle the rest
        currHeights: np.ndarray = heightTable[:, cIdx]
        shouldUpdate, differences = _should_update(rIdx, assign, currHeights.tolist(), reference.tolist(), restEntities, direction)
        if shouldUpdate:
            result.append(assign)
            resultEntities.append(rIdx)
            for entity, difference in zip(restEntities, differences):
                if np.isnan(difference): continue # i.e., we don't touch idle
                if DEBUG and names[rIdx] == 'Daniel A. Keim': print(names[entity], difference, currHeights[entity], assign + (difference*direction))
                result.append(assign + (difference*direction))
                resultEntities.append(entity)
        #if DEBUG and names[rIdx] == 'Daniel A. Keim': print([currHeights[each] for each in restEntities], shouldUpdate, differences, result)
        return resultEntities, result
    
    def _get_block_range(cIdx: int):
        currentBlock = heightTable[block[cIdx], cIdx]
        pointRadius = 2 # 2px is for stroke
        return (np.nanmin(currentBlock) - pointRadius, np.nanmax(currentBlock) + pointRadius) # point radius
    
    def _get_neighbor_index(nums: list[bool|int], val: int|bool, direction:int = 1):
        nums = list(nums)
        if val not in nums: return -1
        return len(nums) - 1 - nums[::-1].index(val) if direction == 1 else nums.index(val)
    
    #NOTE: reference for all and any: https://stackoverflow.com/questions/19601802/how-does-all-in-python-work-on-empty-lists
    def _assign_idle_entity(cIdx: int, rIdx: int, assign: int, assumedDifference: int, orderEntities: list[int], toBeMoved: list[bool], direction=1):
        restEntities: list[int] = orderEntities[toBeMoved] # Same as toBeMovedEntities
        blockRange = _get_block_range(cIdx)
        insideBlock = np.array([(blockRange[0] <= heightTable[each, cIdx]) & (heightTable[each, cIdx] <= blockRange[1]) for each in restEntities])
        notDealt = np.array([dealt.get(each, False) == False for each in restEntities])

        result = []
        resultEntities = []

        # All of them are already dealt with, i.e., we can only insert
        # So we have to check whether the insertion would affect the block
        if all(~notDealt):
            result.append(0)
            resultEntities.append(rIdx)
            for idx, each in enumerate(restEntities):
                resultEntities.append(each)
                currDifference = (heightTable[each, cIdx] - assign) * direction
                minimalDifference = _determine_distance(liner, each, rIdx, None, idle=True)
                if currDifference >= minimalDifference: 
                    result.append(heightTable[each, cIdx] - assign)
                else: break # This insertion affects people
            if (len(result) == len(resultEntities)):
                #print('idle', 'simple insert')
                return resultEntities, result, 'simple insert'
        # All of them are within the block and none of them are dealt with, so we can do assignment by moving them
        elif all(insideBlock) and all(notDealt):
            result.append(0)
            resultEntities.append(rIdx)
            #if names[rIdx] == target: print([names[each] for each in restEntities], assign)
            if direction == -1: restEntities = restEntities[::-1]
            for idx, each in enumerate(restEntities):
                resultEntities.append(each)
                desiredDifference = assumedDifference * direction
                another = restEntities[idx-1] if idx != 0 else orderEntities[_get_neighbor_index(toBeMoved, False, direction)]
                if another in block[cIdx] and each in block[cIdx]: 
                    #print('change')
                    desiredDifference = _determine_distance(liner, another, each, liner.getSessionByID(sessions[cIdx])) * direction
                #print(names[another], names[each], desiredDifference, 'desired')
                result.append(result[-1] + desiredDifference)
            #print('idle', 'simple push')
            return resultEntities, result, 'simple push'
        
        #print(all(insideBlock[notDealt]), any(insideBlock[~notDealt]), assign, names[rIdx])
        # The ones within the block are not dealt with, but we can try pushing
        #print(all(insideBlock[notDealt]) and not any(insideBlock[~notDealt]))
        elif all(insideBlock[notDealt]) and not any(insideBlock[~notDealt]): 
            hypothetical = np.array(heightTable[restEntities, cIdx].copy() + assumedDifference*direction)
            dealtEntities = hypothetical[~notDealt]
            undealtEntities = hypothetical[notDealt]
            dealtBoundary = np.nanmin(dealtEntities) if direction == 1 else np.nanmax(dealtEntities)
            undealtBoundary = np.nanmax(undealtEntities) if direction == 1 else np.nanmin(undealtEntities)
            difference = abs(dealtBoundary - undealtBoundary)
            desiredDifference = 5
            if difference > desiredDifference: # we can push
                result.append(0)
                resultEntities.append(rIdx)
                for idx, each in enumerate(restEntities):
                    resultEntities.append(each)
                    if notDealt[idx]: result.append(hypothetical[idx] - assign)
                    else: result.append(heightTable[restEntities[idx], cIdx] - assign)
                #print('idle', 'whole block push')
                return resultEntities, result, 'whole block push'
            # here means we have to go around
        elif all(insideBlock[notDealt]) and any(insideBlock[~notDealt]): 
            hypothetical = np.array(heightTable[restEntities, cIdx].copy() + assumedDifference*direction)
            move = np.array([False] * len(restEntities))
            moving = range(0, len(restEntities)-1) if direction == 1 else range(len(restEntities)-1, 0, -1)
            begin = 0 if direction == 1 else len(restEntities)-1
            insert = False
            for idx in moving:
                entity = restEntities[idx]
                nextEntity = restEntities[idx+1] if direction == 1 else restEntities[idx-1]
                if idx == begin:
                    minimalDifference = _determine_distance(liner, entity, rIdx, None, idle=True)
                    toBeDifference = (heightTable[entity, cIdx] - assign) * direction
                    if toBeDifference > minimalDifference: 
                        insert = True
                        break
                minimalDifference = _determine_distance(liner, entity, nextEntity, None, idle=True)
                if entity in block[cIdx] and nextEntity in block[cIdx]: minimalDifference = _determine_distance(liner, entity, nextEntity, liner.getSessionByID(sessions[cIdx]))
                toBeDifference = (heightTable[nextEntity, cIdx] - hypothetical[idx]) if direction == 1 else (hypothetical[idx] - heightTable[nextEntity, cIdx])
                #print(names[entity], names[nextEntity], toBeDifference, minimalDifference, 'minimal')
                if toBeDifference > minimalDifference: # we should break
                    if direction == 1: move[:idx+1] = True
                    else: move[idx:] = True
                    break
            #print(move, [names[each] for each in restEntities])
            if any(move) or insert:
                result.append(0)
                resultEntities.append(rIdx)
                for idx, each in enumerate(restEntities):
                    resultEntities.append(each)
                    currDifference = (heightTable[each, cIdx] - assign) * direction
                    minimalDifference = _determine_distance(liner, each, rIdx, None, idle=True)
                    if move[idx]: result.append(hypothetical[idx] - assign)
                    else: result.append(heightTable[each, cIdx] - assign)
                #print('idle', 'partial block push')
                return resultEntities, result, 'partial block push'
        
        # simple push or insert does not work, we just need to update the assign value and insert it
        
        #print([names[each] for each in restEntities], insideBlock, notDealt, assign)
        #print(assign, [names[each] for each in orderEntities], [heightTable[each, cIdx] for each in orderEntities])
        currHeights = np.copy(heightTable[orderEntities, cIdx])
        def _continue_insertion_search(assign: int, currHeights: list[int], baseline: int):
            for height in currHeights:
                if abs(height - assign) < baseline: return True
            return False
        counter = 0
        base = assign
        while _continue_insertion_search(assign, currHeights, assumedDifference):
            negation = 1 if counter % 2 == 0 else -1
            #print(assign, currHeights, direction, negation, (int(counter/2)+1))
            assign = base + assumedDifference*direction*negation*(int(counter/2)+1)
            #print('after', assign)
            counter += 1
            if counter > 10: break
        result = [assign - base]
        resultEntities = [rIdx]
        status = 'idle last insertion'
        return resultEntities, result, status
    
    def _determine_height(rIdx: int, times: list[int], cIdx: int):
        timeline = heightTable[rIdx, times]
        presence = presenceTable[rIdx, :].tolist()
        checkSameSide = True if presenceTable[rIdx, cIdx] == 1 else False # this is for contact
    
        # Find people in the same type of seesions
        [start, end] = _find_same_range(presence, cIdx, heightTable[rIdx, :].tolist(), checkSameSide)
        selection = heightTable[rIdx, start:end]
        #print(timeline, selection, start, end, cIdx, times, names[rIdx])
        if presenceTable[rIdx, cIdx] == -1 and all(np.isnan(selection)): 
            candidates = [heightTable[rIdx, start-1], heightTable[rIdx, end]]
            if _are_on_same_side(candidates[0], candidates[1]): return candidates[0]
            elif (abs(candidates[0]) < abs(candidates[1])): return candidates[0]
            return candidates[1]
        elif presenceTable[rIdx, cIdx] == -1:
            candidates = selection[~np.isnan(selection)]
            return candidates[0]
        #if presenceTable[rIdx, cIdx] == 1:
            #candidates = selection[~np.isnan(selection)]
            #height = candidates[-1]

        #if all(np.isnan(selection)): print(names[rIdx], 'is all nan')
        #height = np.nanmax(selection) if np.sign(selection[0]) == 1 else np.nanmin(selection)
        #print(presence[start:end], heightTable[rIdx, cIdx])
        height = np.nanmax(timeline) if np.sign(timeline[0]) == 1 else np.nanmin(timeline)
        #return height #TODO: improve this
        threshold = 50
        if abs(height - heightTable[rIdx, cIdx]) > threshold: return heightTable[rIdx, cIdx]
            #print(names[rIdx], cIdx, height, heightTable[rIdx, cIdx], 'is too much')
        return height

    for rIdx, times in assign.items():
        #if names[rIdx] == stop: break
        if len(times) == 1: continue # One time point does not need
        dealt[rIdx] = True
        for cIdx in range(times[0], times[-1]+1):
            time = effectiveTimestamps[cIdx]
            label = allTimestamps[time]

            height = _determine_height(rIdx, times, cIdx)
            #print(names[rIdx], label, height)
            # We skip ego and order the heights in an ascending order
            otherHeights, orderedOthers = _get_other_ordered_heights(heightTable[:, cIdx], ego)

            if idleDealt.get(cIdx, None) is None: idleDealt[cIdx] = {}

            if rIdx in orderedOthers: # non idle
                curr = heightTable[rIdx, cIdx]
                # We don't care if it's already the same height or it is crossing
                if curr == height or not _are_on_same_side(curr, height): continue
                order = orderedOthers.tolist().index(rIdx)
                # If it is below, we only care who is below him
                restEntities = orderedOthers[order+1:] if np.sign(height) == 1 else orderedOthers[:order][::-1]
                #restHeights = otherHeights[order+1:] if np.sign(height) == 1 else otherHeights[:order][::-1]
                restEntities, result = _assign_nonidle_entity(rIdx, cIdx, height, curr, referenceTable[:, cIdx], restEntities, np.sign(height))
                # No change, so we don't need to update block range
                if len(result) == 0: 
                    outcome = 'nonidle cannot be assigned'
                    status = 'did not change'
                    #print(names[rIdx], label, 'nonidle cannot be assigned')
                    continue
                #print([names[each] for each in restEntities], result)
                heightTable[restEntities, cIdx] = result
                outcome = 'nonidle assigned'
                status = 'changed'
                #print(names[rIdx], label, 'nonidle assigned')
            else: # idle sessions
                idleDealt[cIdx][rIdx] = True
                SQUEEZE_LINE = 2 #1.75
                # Minimum distance we want it to have from other entities
                assumedDifference = SQUEEZE_LINE # DISTANCE_LINE
                # Add this so that we can capture those that are out of range but did not have enough distance to the assignment
                detectRange = otherHeights + SQUEEZE_LINE*np.sign(height)
                #print([names[each] for each in orderedOthers], detectRange, height, names[rIdx], label)
                toBeMoved = (detectRange > height) if np.sign(height) == 1 else (detectRange < height)
                hasContactNodes = [each for each in orderedOthers[toBeMoved] if (presenceTable[each, cIdx] == 1 or heightTable[each, cIdx] == height)]
                # We don't need to worry about the assignment because either no one gets affected or only idle sessions are affected.
                #print(sum(toBeMoved), hasContactNodes)
                #TODO: it feels like there is bug here?
                if sum(toBeMoved) == 0 or len(hasContactNodes) == 0: 
                    outcome = 'idle assignment has no effect'
                    status = 'no effect'
                    #print(names[rIdx], label, 'idle assignment has no effect')
                    heightTable[rIdx, cIdx] = height
                    continue 
                toBeMovedEntities = [names[each] for each in orderedOthers[toBeMoved]]
                contactEntities = [names[each] for each in hasContactNodes]
                #print(names[rIdx], label, 'idle can affect', toBeMovedEntities, 'where there are', contactEntities)

                restEntities, result, status = _assign_idle_entity(cIdx, rIdx, height, assumedDifference, orderedOthers, toBeMoved, np.sign(height))
                if len(result) == 0: continue
                #print('before', heightTable[rIdx, cIdx], heightTable[restEntities, cIdx], [names[each] for each in restEntities])
                #heightTable[rIdx, cIdx] = height
                #print(result, height)
                heightTable[restEntities, cIdx] = height + result
                #print(names[rIdx], label, 'idle assigned')
                outcome = 'idle assigned'
            if DEBUG:
                newHeights = heightTable[~np.isnan(heightTable[:, cIdx]), cIdx].copy()
                newHeights = np.sort(newHeights)
                for idx, each in enumerate(newHeights):
                    if idx == 0: continue
                    if abs(each - newHeights[idx-1]) < 1.75:
                        print('ERROR', names[rIdx], label, each, newHeights[idx-1], outcome, status)
                        break
    #TODO: we can smooth this
    
    return heightTable


def _get_other_ordered_heights(heights, ego):
    otherHeights, orderedOthers = np.sort(heights), np.argsort(heights)
    nanFilter = ~np.isnan(heights[orderedOthers]) & (orderedOthers != ego)
    return otherHeights[nanFilter], orderedOthers[nanFilter]


def _determine_distance(liner, currIdx: str, prevIdx: str, session=None, idle=False):
    colors = liner._line_color
    names = liner.entities_names
    distance = DISTANCE_LINE
    SQUEEZE_LINE = DISTANCE_LINE
    if liner._config.get('squeezeSameCategory'): SQUEEZE_LINE = 2
    if colors.get(names[currIdx], '') == colors.get(names[prevIdx], 'na'): distance = SQUEEZE_LINE
    if idle: return SQUEEZE_LINE
    if session is None: return distance
    result = _have_different_identity(session, names[currIdx], names[prevIdx])
    if result == 'ego 2-level' or result == 'different': distance = DISTANCE_HOP
    if result == 'ego 1-level': distance = DISTANCE_LINE
    return distance

def _compute_session_height_space(liner, slots: np.ndarray, slotsInEntities: np.ndarray, egoSlotIdx: int, through=True):
    span = liner.span
    (numEntities, numTimestamps) = span
    heightTable = np.full(span, np.nan)
    ego = liner.egoIdx
    names = liner.entities_names
    colors = liner._line_color

    blockRange = np.full((2, numTimestamps), -1)
    # This only aligns the ego sessions
    for cIdx in range(0, numTimestamps):
        entities: np.ndarray = slotsInEntities[egoSlotIdx, cIdx]
        sessionID: int = slots[egoSlotIdx, cIdx]
        session: Session = liner.getSessionByID(sessionID)
        egoIdx = entities.tolist().index(ego)

        # Initialize the distances among entities in the ego session at each timestamp
        heights = [0]
        for idx, rIdx in enumerate(entities):
            if idx == 0: continue
            distance = _determine_distance(liner, rIdx, entities[idx-1], session)
            heights.append((heights[-1] + distance))
        heights = np.array(heights)
        heights -= heights[egoIdx] # So that the ego is always at 0 

        #if cIdx == 35:
        #    print(heights, [names[each] for each in entities])

        if cIdx == 0: 
            blockRange[:, cIdx] = [np.nanmin(heights), np.nanmax(heights)]
            heightTable[entities, cIdx] = heights
            continue

        # Compare with the heights at previous timestamp, enforce the entities to stay on the same height if that is possible
        previousHeights = heightTable[entities, cIdx - 1]
        #heights = _attempt_to_reduce_wiggles(liner, previousHeights, heights, entities, slots[egoSlotIdx, cIdx-1], session)

        blockRange[:, cIdx] = [np.nanmin(heights), np.nanmax(heights)]
        heightTable[entities, cIdx] = heights
    
    heightTable = _compute_idle_session_height(liner, heightTable, slots, slotsInEntities, egoSlotIdx, blockRange, through=through)

    #_debug(liner, heightTable)
    return heightTable

#NOTE: might not be needed
def _attempt_to_reduce_wiggles(liner, previousHeights, heights, entities, prevSessionID, session):
    currHeights = heights.copy()
    names = liner.entities_names
    for idx, prev in enumerate(previousHeights):
        curr = currHeights[idx]
        # Skip, if they are already the same, or one of them is not supposed to be plotted.
        if prev == curr or np.isnan(prev) or np.isnan(curr): continue
        # Skip, if the height from the previous timestamps is already taken in this one
        if prev in currHeights: continue
        rIdx = entities[idx]
        prevSession = liner.getSessionByID(prevSessionID)
        currIdentity = session.getIdentity(names[rIdx])
        prevIdentity = prevSession.getIdentity(names[rIdx])
        # We only move it to the previous height if the identity is the same in the previous and current session
        direction = (curr < prev) # np.sign(curr) = 1, i.e., below the ego
        if np.sign(curr) == -1: direction = (curr > prev)
        #TODO: if the direction is false, we have to check whether they are moving up in the same group of identity without violating the ordering
        if (currIdentity == prevIdentity) and direction:
            print(currHeights, 'change', currHeights[idx], 'to', prev)
            currHeights[idx] = prev
            for nextIdx in range(idx+1, len(heights)):
                nextHeight = currHeights[nextIdx]
                if nextHeight == 0:# We cannot move ego
                    currHeights[idx:] = heights[idx:]
                    break
                distance = heights[nextIdx] - heights[nextIdx-1]
                diff = (nextHeight - currHeights[nextIdx-1])*np.sign(curr)
                update = currHeights[nextIdx-1] + distance
                #print(nextHeight, 'move to', update, 'because of', currHeights[nextIdx-1])
                #print('current distance', diff, 'supposed', distance)
                if diff < distance: currHeights[nextIdx] = update
            #print(currHeights, 'final')
    return currHeights

def _debug(liner, heightTable):
    (numEntities, numTimestamps) = liner.span
    ego = liner.egoIdx
    names = liner.entities_names
    colors = liner._line_color
    allGroups = liner._groups
    effectiveTimestamps = liner.effective_timestamps
    allTimestamps = liner._all_timestamps

    for cIdx in range(0, numTimestamps):
        time = effectiveTimestamps[cIdx]
        label = allTimestamps[time]
        groups = allGroups.get(label, [])
        entities = [names.index(hop) for group in groups for hop in group]
        existIndices = np.where(np.isnan(heightTable[:, cIdx]) == False)[0]
        heights = np.sort(heightTable[existIndices, cIdx])
        order = np.argsort(heightTable[existIndices, cIdx])
        #print(heightTable[entities, cIdx], groups, cIdx, label) # found bug
        #heights = heightTable[entities, cIdx]
        #check = len(np.nonzero(heightTable[:, cIdx] == -1)[0])
        #print(check, heights.shape, len(names), label) # check + heights.shape[0] == len(names)

def _have_different_identity(session, oneEntity, otherEntity):
    if not isinstance(session, Session): return False
    identity = session.getIdentity(oneEntity)
    otherIdentity = session.getIdentity(otherEntity)
    result = 'same'
    if identity != otherIdentity: result = 'different'
    if 2 in [identity, otherIdentity]:
        if abs(identity - otherIdentity) == 1: result = 'ego 1-level'
        if abs(identity - otherIdentity) == 2: result = 'ego 2-level'
    return result

def _is_pair_of_one_hop_two_hop(session, currEntityName, aboveEntityName):
    if not isinstance(session, Session): return False
    hops = session.hops
    twoHops = hops[0] + hops[4]
    if (currEntityName not in twoHops) and aboveEntityName in twoHops: return True
    if (currEntityName in twoHops) and aboveEntityName not in twoHops: return True
    return False

def _is_hops(session, name):
    if not isinstance(session, Session): return False
    hops = session.hops
    twoHops = hops[0] + hops[4]
    return name in twoHops
