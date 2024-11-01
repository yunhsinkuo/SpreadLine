import numpy as np
from itertools import groupby
import math
from sklearn.neighbors import KernelDensity
from scipy.signal import argrelextrema
from SpreadLine.utils import Node, Session, Entity, Path

TIME_UNIT = 10 

#TODO: rescale the width
#TODO: remove the last day in allTimestamps

# Type definitions: types.ts

def rendering(size, liner):
    renderer = Renderer()    
    renderer.fit(size, liner)
    return renderer.render

class Renderer():
    def __init__(self):
        self.origin = []
        self.heights = []
        self.render = { # screen pixels
            'bandWidth': 0,
            'blockWidth': 40, # maybe the 8x of the circle size?
            "ego": '',
            'timeLabels': [],
            'storylines': [], 
            'blocks': [],
            'heightExtents': [0, 0],
        }
        self.scaleTimer = {
            'bandWidth': -1,
            'allTimeLabels': [], # All posX of each time label, where the order is consistent with allTimestamps
            'allBlocks': [], # The starting posX and ending posX for each block, shorter width compared to bands
            'allBands': [], # The starting posX and ending posX for each timestamp
        }
        self.labelTable = None
        self.blockRange = None
        self.aggregateTable = None
        self.fitToHeight = False
        #self.bundle = {
        #    "idle": True,
        #    "nonIdle": False,
        #    "level": "tangent", # "tangent", "start", "end",
        #    "all": True,
        #}
    
    def fit(self, screenSize, liner):
        span = liner.span
        width, height = screenSize.get('width'), screenSize.get('height')
        self.fit_time(width, liner._all_timestamps, liner._config.get('bandStretch'))
        self.fit_entities(span, height, liner._tables.get('presence'), liner._tables.get('height'), liner.effective_timestamps)

        self.prepare_time_labels(liner._all_timestamps)
        self.prepare_line_segments(liner)
        #self.prepare_labels_line_segments(liner)
        self.prepare_points_blocks(liner)
        self.prepare_labels(liner)
        self.prepare_inline_labels(liner.entities_names)
        #self.bundle_lines(liner)
        self.render.update({'ego': liner.entities_names[liner.egoIdx]})


    def fit_time(self, width: int, domain: np.ndarray, bandStretch: list[list[str]]):
        """
        Computes the horizontal positioning of all the timestamps by emulating d3.scaleBand(), i.e., each timestamp takes a band
        """
        # Identify which timestamps need to be stretched
        domainSize = len(domain)
        toBeStretched = []
        for [start, end] in bandStretch:
            startIdx = domain.index(start) if start != '' else 0
            endIdx = domain.index(end) if end != '' else domainSize-1
            toBeStretched.extend(list(range(startIdx, endIdx+1)))

        # This is to follow d3.scaleband(), https://observablehq.com/@d3/d3-scaleband
        align = 0.5 # this is fixed here, controlling the space on the ends of the bands (close to padding)
        # range is width here
        # range = domainSize*bandwidth + (domainSize-1)*gap + step*paddingOuter*2 
        # range = step*domainSize + step*(paddingOuter*2 - paddingInter)
        # bandwidth = step - gap
        # gap = step * paddingInter
        # outerpadding = left-pad + right-pad = step*paddingOuter*2
        # leftPad = step * paddingOuter * align * 2
        # rightPad = step * paddingOuter * (1-align) * 2
        paddingInter = 0.2
        paddingOuter = 0.1
        #TODO: this won't fit into the screen when we stretch some bands
        #TODO: should leave space for labels text
        step: float = np.round(np.divide(width, (domainSize + paddingOuter*2 - paddingInter)), 2)
        gap: float = step * paddingInter
        bandwidth: float = step - gap
        paddingLeft: float = step * paddingOuter * align * 2
        paddingRight: float = step * paddingInter * (1-align) * 2

        bandStart: np.ndarray = np.full(domainSize, 0)
        bandStart[0] = paddingLeft
       
        for idx in range(1, domainSize):
            additional = 0
            if idx in toBeStretched: additional = step * 1.1
            bandStart[idx] = bandStart[idx-1] + step + additional
        
        bands = np.vstack((bandStart, bandStart + bandwidth)).T # [[start, end]]
        #NOTE: the block width would be bandwith weighted by something between 0 and 1
        # + np.divide(bandwidth, 2) # middle point for labelling

        blockWeight = 0.6
        # Set the maximum block width to be 8 times of the circle size.
        if blockWeight * bandwidth < self.render['blockWidth']:
            self.render.update({'blockWidth': blockWeight * bandwidth})
        else:
            blockWeight = self.render['blockWidth'] / bandwidth
            
        blockSideWeight = (1 - blockWeight) / 2
        blocks = np.vstack((bandStart + bandwidth * blockSideWeight, bandStart + bandwidth* (1 - blockSideWeight))).T

        self.scaleTimer.update({
            'allTimeLabels': bandStart + np.divide(bandwidth, 2),
            'allBands': bands,
            'allBlocks': blocks,
            'bandWidth': bandwidth,
        })
        self.render.update({'bandWidth': bandwidth})

    # find their height first, then deal with the line in later
    def fit_entities(self, span, height, validTable, heightTable, validDomain):
        # TODO: check why we need 60 in this case
        heights: np.ndarray = (heightTable+1)*6# + 60
        # scale up to screen pixels
        if self.fitToHeight:
            maxVal = np.max(heightTable)
            heights = np.round(heightTable / maxVal * height + 60, 2) 

        #aggregateTable = np.full(span, 0)
        #heights, aggregateTable = _unstack_same_height(heights)

        topY = np.nanmin(heights)
        bottomY = np.nanmax(heights)
        self.render.update({'heightExtents': [topY, bottomY]})
        self.heights = heights

        entity = np.full(span, 0, dtype=object)
        markers = self.scaleTimer.get('allBlocks')[validDomain] # [[start, end]]
        for rIdx in range(0, span[0]):
            for cIdx in range(0, span[1]):
                if validTable[rIdx, cIdx] == 0: # 1 if the entity exists; 0, otherwise
                    entity[rIdx, cIdx] = np.array([-1, -1])
                    continue
                x: [float, float] = markers[cIdx] # in pixels #NOTE: this was the middle points, it is now [start, end]
                y: float = heights[rIdx, cIdx] # in pixels
                entity[rIdx, cIdx] = np.array([x, y], dtype=object)
        self.origin = entity
        #self.aggregateTable = aggregateTable

    def prepare_time_labels(self, timeLabels):
        labelPos = self.scaleTimer.get('allTimeLabels')
        assert len(labelPos) == len(timeLabels), "Inconsistent time points"
        self.render.update({
            'timeLabels': [ {"label": label, "posX": pxl}  for (pxl, label) in zip(labelPos, timeLabels)][:-1]
        })

    def prepare_line_segments(self, liner):
        ego: int = liner.egoIdx
        names: list[str] = liner.entities_names
        color: dict = liner._line_color
        timestamps = liner._all_timestamps
        effective_timestamps = liner.effective_timestamps
        (numEntities, numTimestamps) = self.origin.shape
        labelTable = np.full((numEntities, numTimestamps), -1)
        sideTable = liner._tables.get('crossing')
        result = []

        for rIdx in range(0, numEntities):
            marks = self.origin[rIdx]
            invalidity = np.array([np.array_equal(each, np.array([-1, -1])) if each.dtype!='O' else False for each in marks])
            #TODO: using original way to get the color will cause bugs, e.g., someone in 2008 but the timeList computes 2005 instead
            valids = np.nonzero(~invalidity)[0]
            lines = []

            lineColor ='#424242' if (rIdx == ego) else color.get(names[rIdx], '#424242')
            lifeStart, lifeEnd = valids[0], valids[-1]

            chunk = {
                "name": names[rIdx],
                "lines": [], 
                "marks": [{'posX': 0, 'posY': 0, 'name': names[rIdx], 'size': 0}, {'posX': 0, 'posY': 0, 'name': names[rIdx], 'size': 0}],
                "label": {'posX': 0, 'posY': 0, 'name': '', 'textAlign': 'start', 'line': '', 'label': ''},
                "inlineLabels": [],
                "color": lineColor,
                "id": rIdx,
                "lifespan": int(effective_timestamps[lifeEnd] - effective_timestamps[lifeStart]) + 1,
                'crossingCheck': False if sideTable[rIdx] == 0 else True,
            }

            if len(valids) == 1: 
                result.append(chunk)
                continue # only one point

            validLines = marks[valids]
            crossingCheck = set([np.sign(each[1]) for each in validLines])

            for idx, cIdx in zip(range(1, len(validLines)), valids[1:]):
                svgString = ''
                leftPosY = validLines[idx - 1][1]
                rightPosY = validLines[idx][1]
                [leftStart, leftEnd] = validLines[idx - 1][0]
                [rightStart, rightEnd] = validLines[idx][0]
                start = [leftStart, leftPosY]
                end = [rightEnd, rightPosY]
                if idx == 1: start = [0.5*(leftStart + leftEnd), leftPosY] # make it start from the middle
                if idx == len(validLines)-1: end = [0.5*(rightStart + rightEnd), rightPosY] # make it end in the middle

                if leftPosY == rightPosY: # straight line
                    labelTable[rIdx, valids[idx]] = valids[idx] # end
                    svgString = f'M{_to_svg_join(start)} L{_to_svg_join([rightStart, rightPosY])}'
                else: # bezier line
                    control1, control2 = _compute_bezier_line([leftEnd, leftPosY], [rightStart, rightPosY])
                    svgString = f'M{_to_svg_join(start)} L{_to_svg_join([leftEnd, leftPosY])}'
                    svgString += f' C{_to_svg_join(control1)} {_to_svg_join(control2)} {_to_svg_join([rightStart, rightPosY])}'
                lines.append(svgString)
            
            self.labelTable = labelTable
            chunk.update({'lines': lines})
            result.append(chunk)
        self.render.update({'storylines': result})

    def prepare_labels(self, liner):
        storylines = self.render.get('storylines')
        ego: int = liner.egoIdx
        names: list[str] = liner.entities_names
        timestamps = liner._all_timestamps
        (numEntities, numTimestamps) = self.origin.shape
        blockRanges = self.blockRange

        for rIdx in range(0, numEntities):
            marks = self.origin[rIdx]
            invalidity = np.array([np.array_equal(each, np.array([-1, -1])) if each.dtype!='O' else False for each in marks])
            valids = np.nonzero(~invalidity)[0]
            update = storylines[rIdx]
            lineStart: [[float, float], float] = marks[valids[0]]
            lineEnd : [[float, float], float] = marks[valids[-1]]
            startVisible = 'visible'
            endVisible = 'visible'

            #if self.aggregateTable[rIdx, valids[0]] != 0: startVisible = 'hidden'
            #if self.aggregateTable[rIdx, valids[-1]] != 0: endVisible = 'hidden'

            # Part 1. prepare entity marks
            h = 7 # height of the equilateral triangle, in pixels
            a = 2*h/math.sqrt(3) # h = math.sqrt(3) / 2 * a
            area = math.sqrt(3) / 4 * a * a
            symbolMarks = []
            if (rIdx != ego):
                startMark = {'posX': lineStart[0][0] - h/2, 'posY': lineStart[1], 'name': names[rIdx], 'size': area, 'visibility': startVisible}
                endMark = {'posX': lineEnd[0][1] + h/2, 'posY': lineEnd[1], 'name': names[rIdx], 'size': area, 'visibility': endVisible}
                symbolMarks = [startMark, endMark]

            # Part 2. prepare entity labels
            dx = 12 # NOTE: 12 pixels apart
            dxOffset = 10
            markOffset = 2
            others = (np.array(range(0, numEntities)) != rIdx).nonzero()
            prevTimestamp = min([valids[0]-1, 0])
            nextTimestamp = min([numTimestamps-1, valids[-1]+1])
            #print(valids[0], self.heights[others, valids[0]+1], lineStart[1], lineStart[1] in self.heights[others, valids[0]+1])
            label = {"posX": lineStart[0][0] - dx, "posY": lineStart[1], "textAlign": "end", 
                     'line': f'M{_to_svg_join([lineStart[0][0] - dxOffset, lineStart[1]])} L{_to_svg_join([lineStart[0][0] - markOffset, lineStart[1]])}'} # marks[valids[0]]: [posX: [start, end], posY]
            # labels should be put at the end of lines, or this init label position blocks the previous timestamp
            extents = blockRanges[:, prevTimestamp]
            # valids[0] > (numTimestamps/2) 
            if (extents[0] <= lineStart[1] and lineStart[1] <= extents[1] and valids[0] != 0): 
                if names[rIdx] == 'Russell Brand': #FAG
                    label = {"posX":  lineEnd[0][1] + dx, "posY": lineEnd[1], "textAlign": "start",
                            'line': f'M{_to_svg_join([lineEnd[0][1] + markOffset, lineEnd[1]])} L{_to_svg_join([lineEnd[0][1] + dxOffset, lineEnd[1]])}'}
                if (lineEnd[1] in self.heights[others, nextTimestamp]):
                    label.update({"posX": lineStart[0][0] - dx, "posY": lineStart[1], "textAlign": "end",
                                  'line': f'M{_to_svg_join([lineStart[0][0] - dxOffset, lineStart[1]])} L{_to_svg_join([lineStart[0][0] - markOffset, lineStart[1]])}'})
            label.update({"label": names[rIdx], 'visibility': startVisible if label["textAlign"] == "end" else endVisible})

            update.update({'marks': symbolMarks, 'label': label})
            storylines[rIdx] = update
        self.render.update({'storylines': storylines})
    #TODO: change all the "label" to "name" if it is referring to entity names
    def prepare_points_blocks(self, liner):
        validDomain = liner.effective_timestamps
        sessions = liner.sessions
        names = liner.entities_names
        timeLabels = liner._all_timestamps
        context = liner.context
        nodeContext = liner._node_color
        nodeContext.set_index(keys=['time', 'entity'], inplace=True)
        #print(nodeContext.index)

        (numEntities, numTimestamps) = self.origin.shape
        blockRender = []
        pointRender = []
        validLabels = [each.timestamp for each in sessions]
        layout = context['layout']


        blockRange = np.full((2, numTimestamps), -1)
        blocks = self.scaleTimer.get('allBlocks')[validDomain]
        validBlocks = self.scaleTimer.get('allBlocks')[validLabels]
        width = self.render.get('blockWidth', 0)
        aggregateIDCounter = 0
        for cIdx in range(0, numTimestamps): # NOTE: assumption that only one non-idle session at one time
            if blocks[cIdx] not in validBlocks: continue
            tIdx = np.where(self.scaleTimer.get('allBlocks') == blocks[cIdx])[0][0]
            session: Session = list(filter(lambda x: x.timestamp == tIdx, sessions))[0]
            timestamp = session.timestamp
            entities: list[int] = session.getEntityIDs()
            self.labelTable[entities, cIdx] = -1
            hops = [list(map(lambda x: names.index(x), hop)) for hop in session.hops]

            # [[start, end], yPos]
            #width = blocks[cIdx][1] - blocks[cIdx][0]
            points = [{
                'id': int(idx),
                'posX': float(0.5*(each[0][0] + each[0][1])),
                'posY': float(each[1]),
                'name': names[idx],
                'group': len(blockRender),
                'aggregateGroup': 0, #int(self.aggregateTable[idx, cIdx]),
                'visibility': 'visible' #if self.aggregateTable[idx, cIdx] == 0 else 'hidden',
            } for idx, each in zip(entities, self.origin[entities, cIdx])]

            blockOutline, moveX = _compute_block(points, hops, width)
            # leave a 7.5% white space for each side as a gap
            [minPoint, maxPoint] = getExtents(points, key=lambda x: x['posY'])
            #minPosY = minPoint['posY']
            #height = width * 0.85
            #height = abs(maxPoint['posY'] - minPosY) * 0.85 
            blockRange[:, cIdx] = [minPoint['posY'] - 5, maxPoint['posY'] + 5] # the block range 

            for point in points:
                scaleX = 0
                scaleY = 0
                label = -1
                #print(timeLabels[timestamp], point['name'])
                #print(nodeContext, timeLabels[timestamp], point['name'])
                if (point['name'], timestamp) in layout.index:
                    match = layout.loc[(point['name'], timestamp), :]
                    scaleX = match['posX']
                    scaleY = match['posY']
                if (timeLabels[timestamp], point['name']) in nodeContext.index:
                    #print('da fa')
                    node = nodeContext.loc[(timeLabels[timestamp], point['name']), :]
                    label = str(node['context'])
                point.update({'scaleX': scaleX, 'scaleY': scaleY, 'label': label})
            #TODO: implement point collision, saw stackoverflow say force-directed layout is expensive
            pointRender.extend(points)

            links = []
            for (source, target, weight) in session.links:
                sourceSearch = list(filter(lambda x: x['name'] == source, points))
                targetSearch = list(filter(lambda x: x['name'] == target, points))
                if len(sourceSearch) == 0 or len(targetSearch) == 0: 
                    print(source, target)
                sourcePoint = list(filter(lambda x: x['name'] == source, points))[0]
                targetPoint = list(filter(lambda x: x['name'] == target, points))[0]
                links.append(tuple([sourcePoint['id'], targetPoint['id']]))
            
            block = {
                'id': len(blockRender),
                'time': timeLabels[timestamp],
                "outline": blockOutline,
                'names': [names[each] for each in entities],
                'relations': links,
                'points': points,
                'moveX': moveX, # height and width for the expanded block
                'topPosY': min(points, key=lambda x: x['posY'])['posY'],
            }
            blockRender.append(block)
        
        self.blockRange = blockRange
        self.render.update({"blocks": blockRender}) #'points': pointRender

    def prepare_inline_labels(self, names):
        (numEntities, numTimestamps) = self.labelTable.shape
        storylines = [each['name'] for each in self.render.get('storylines')]
        #print(len(storylines), 'yo')
        for rIdx in range(0, numEntities):
            result = []
            marks = self.origin[rIdx, :]
            name = names[rIdx]
            storylineIdx = storylines.index(name)
            candidates = []

            for cIdx in range(0, numTimestamps):
                if self.labelTable[rIdx, cIdx] == -1: continue
                [_, posY] = marks[cIdx]
                extents = self.blockRange[:, cIdx]
                if extents[0] < posY and posY < extents[1]: self.labelTable[rIdx, cIdx] = -1

            for _, group in groupby(enumerate(self.labelTable[rIdx, :]), lambda x: x[0] - x[1]):
                members = [val for (_, val) in list(group)]
                if len(members) >= 3: candidates.append(members)
            for slots in candidates:
                mid = math.floor(0.5*len(slots))
                #print(slots[mid], slots)
                targetIdx = slots[mid]
                [[start, end], posY] = marks[targetIdx]
                result.append({
                    "posX": 0.5*(start + end),
                    "posY": posY,
                    "name": name,
                })
            self.render.get('storylines')[storylineIdx].update({'inlineLabels': result})

def _unstack_same_height(heightTable: np.ndarray):
    gap = 2.5
    (numEntities, numTimestamps) = heightTable.shape
    aggregateTable = np.full((numEntities, numTimestamps), 0)
    for cIdx in range(0, numTimestamps): #NOTE: skip the very first one because it might not happen
        heights = heightTable[:, cIdx]
        uniqueHeights, counts = np.unique(heights, return_counts=True)
        dups = uniqueHeights[counts > 1]
        group = 1
        for height in dups:
            if height == 0: continue
            entities = np.where(heights == height)[0]
            if cIdx == 0: order = (heightTable[entities, cIdx + 1] - heightTable[entities, cIdx]).argsort()[::-1] 
            else: order = (heightTable[entities, cIdx] - heightTable[entities, cIdx - 1]).argsort()
            aggregateTable[entities, cIdx] = group
            # These should be ordered in descending order, positive -> 0 -> negative
            counter = 1
            for each in entities[order].tolist()[1:]:
                #sign = 1 if counter % 2 == 0 else -1
                #update = height + gap * np.ceil(counter/2) * sign
                update = height - gap * counter
                #if update in heights: print('yo, duplicate heights')
                heightTable[each, cIdx] = update
                #print(each, height, heightTable[each, :])
                counter += 1
            group += 1
    return heightTable, aggregateTable

def _1d_cluster_kde(numbers, indices, bandwidth=1):
    #print(indices, numbers)
    sample = np.linspace(min(numbers), max(numbers))
    nested_numbers = np.array(numbers).reshape(-1, 1)
    kde = KernelDensity(kernel='gaussian', bandwidth=bandwidth).fit(nested_numbers)
    estimate = kde.score_samples(sample.reshape(-1,1))
    minima, maxima = argrelextrema(estimate, np.less)[0], argrelextrema(estimate, np.greater)[0]
    minima = sample[minima]
    if len(minima) == 0 and len(maxima) == 0: # either they are all the same, or the sample size is too small that cannot build clusters
        if len(set(numbers)) == 1: return [indices]#[numbers]
        else: return [[each] for each in indices]#[[each] for each in numbers]
    if len(minima) == 0: return [indices]#[numbers]
    indices = np.array(indices).reshape(-1, 1)
    if len(minima) == 1: #return [nested_numbers[nested_numbers< minima[0]].tolist(), nested_numbers[nested_numbers >= minima[0]].tolist()]
        #print([indices[nested_numbers< minima[0]].tolist(), indices[nested_numbers >= minima[0]].tolist()], numbers, 'here')
        return [indices[nested_numbers< minima[0]].tolist(), indices[nested_numbers >= minima[0]].tolist()]
    result = []
    for idx in range(0, len(minima)):
        if idx == 0: 
            result.append(indices[nested_numbers < minima[idx]].tolist())
        if idx +1 <= len(minima) - 1:
            result.append(indices[(nested_numbers >= minima[idx]) & (nested_numbers < minima[idx+1])].tolist())
        if idx == len(minima) - 1:
            result.append(indices[nested_numbers >= minima[idx]].tolist())
    return result

def _compute_tangent(row):
    [x1, y1] = row['start']
    [x2, y2] = row['end']
    dy = y2 - y1
    dx = x2 - x1
    dr = round(math.sqrt(dy**2 + dx**2), 2)
    # normalized vector
    dy = dy / dr
    dx = dx / dr
    return dy/dx

def _compute_block(points, hops: list[list[int]], blockWidth, portion=0.35):
    # hops: [[2-hop nodes], [1-hop sources], [ego], [1-hop targets], [2-hop nodes]]
    radius = blockWidth / 2
    [topPosY, bottomPosY] = getExtents(points, key=lambda x: x['posY'])
    posX = points[0]['posX'] # all elements' posX should be the same
    width = abs(bottomPosY['posY'] - topPosY['posY']) # this shall be the size of the expanded block

    result = _compute_button_and_bars_in_block(posX, topPosY['posY'], bottomPosY['posY'], radius, width)

    leftArc = Path()
    rightArc = Path()
    offset = 0.005 # otherwise there might be 1px gap
    # from the top to the bottom
    topHops = list(filter(lambda x: x['id'] in hops[0], points))
    main = list(filter(lambda x: x['id'] in (hops[1] + hops[2] + hops[3]), points))
    [topMain, bottomMain] = getExtents(main, key=lambda x: x['posY'])
    bottomHops = list(filter(lambda x: x['id'] in hops[4], points))

    if len(hops[0]) == 0:
        leftArc.arc(posX, topMain['posY'], radius, math.pi * (1.5 + offset), math.pi, 1)
        rightArc.arc(posX, topMain['posY'], radius, math.pi * (1.5 - offset), 0)
    else:
        [topTopHop, bottomTopHop] = getExtents(topHops, key=lambda x: x['posY'])
        # Main block for the two-hop neighbors at top
        leftArc.arc(posX, topTopHop['posY'], radius, math.pi * (1.5 + offset), math.pi, 1).arc(posX, bottomTopHop['posY'], radius, math.pi, math.pi * (1 - portion + offset), 1)
        rightArc.arc(posX, topTopHop['posY'], radius, math.pi * (1.5 - offset), 0).arc(posX, bottomTopHop['posY'], radius, 0, math.pi * (portion + offset))
        # Connect to the main block
        leftArc.arc(posX, topMain['posY'],radius, math.pi * (1+portion), math.pi, 1)
        rightArc.arc(posX, topMain['posY'], radius, -math.pi*portion, 0)

    if len(hops[4]) == 0:
        leftArc.arc(posX, bottomMain['posY'], radius, math.pi, math.pi * (0.5 - offset), 1)
        rightArc.arc(posX, bottomMain['posY'], radius, 0, math.pi * (0.5 + offset))
    else:
        [topBottomHop, bottomBottomHop] = getExtents(bottomHops, key=lambda x: x['posY'])
        leftArc.arc(posX, bottomMain['posY'], radius, math.pi, math.pi * (1 - portion + offset), 1)
        rightArc.arc(posX, bottomMain['posY'], radius, 0, math.pi * (portion+ offset))
        leftArc.arc(posX, topBottomHop['posY'], radius, math.pi*(1 + portion), math.pi, 1).arc(posX, bottomBottomHop['posY'], radius, math.pi, math.pi*(0.5 - offset), 1)
        rightArc.arc(posX, topBottomHop['posY'], radius, -math.pi*portion, 0).arc(posX, bottomBottomHop['posY'], radius, 0, math.pi * (0.5 + offset))

    result.update({'left': leftArc.toString(), 'right': rightArc.toString()})
    return result, width


def getExtents(array: list, key=lambda x: x) -> list:
    if len(array) == 0: return []
    return [min(array, key=key), max(array, key=key)]

def _compute_button_and_bars_in_block(posX: int, topPosY: int, bottomPosY: int, radius: int, width: int) -> dict:
    """
    Computes the button and horizontal bars in a block.

    Args:
        posX (int): The x-coordinate of the block.
        topPosY (int): The y-coordinate of the top of the block.
        bottomPosY (int): The y-coordinate of the bottom of the block.
        radius (int): The radius of the block.
        width (int): The width of the block.

    Returns:
        dict: A dictionary containing the button and horizontal bars in the block.
    """
    
    height = 18 # screen pixels
    buttonWidth = 60 #TODO: measure the textwidth though
    button = { # Button
        'width': buttonWidth,
        'height': height,
        'posX': posX,
        'posY': bottomPosY + radius
    }
    result = {'button': button}

    topHorizontalBar = Path()
    bottomHorizontalBar = Path()
    topHorizontalBar.moveTo(posX, topPosY - radius).lineTo(posX + width, topPosY - radius)
    bottomHorizontalBar.moveTo(posX, bottomPosY + radius).lineTo(posX + width, bottomPosY+ radius)
    result.update({'top': topHorizontalBar.toString(), 'bottom': bottomHorizontalBar.toString()})
    return result

def _compute_bezier_line(start, end):
    width = np.abs(end[0] - start[0])
    height = np.abs(end[1] - start[1])
    ratio = np.round(width / height, 2)
    if ratio >= 0: # was 0.3
        midX = (start[0] + end[0]) * 0.5
        control1 = np.array([midX, start[1]])
        control2 = np.array([midX, end[1]])
    #else: #do a different control points when the width between start and end are too narrow
    #    higher = start[1]
    #    if start[1] > end[1]: higher = end[1]
    #    weight = 0.5
    #    control1 = np.array([end[0], higher + weight*height])
    #    control2 = np.array([start[0], higher + (1-weight)*height])
    return control1, control2

def _to_svg_join(points: np.ndarray|list):
    return ','.join(np.array(points).astype(str))
