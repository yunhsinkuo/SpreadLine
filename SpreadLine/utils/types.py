import math

tau = 2 * math.pi
epsilon = 1e-6
tauEpsilon = tau - epsilon

# This is most of d3.path()
class Path():
    def __init__(self):
        # The start of current subpath
        self.startX: int = None # this._x0
        self.startY: int = None # this._y0
        # The end of current subpath
        self.endX: int = None  # this._x1
        self.endY: int = None # this._y1
        self.str = ''
        self.curve = 0.5

    def __str__(self):
        return self.str
    
    def moveTo(self, x: int, y: int):
        self.startX = +x
        self.startY = +y
        self.endX = +x
        self.endY = +y
        self.str += f'M{+x},{+y}'
        return self

    def lineTo(self, x: int, y: int):
        self.endX = +x
        self.endY = +y
        self.str += f'L{self.endX}, {self.endY}'
        return self

    def quadraticCurveTo(self, x1: int, y1: int, x: int, y: int):
        self.endX = +x
        self.endY = +y
        self.str += f'Q{+x1}, {+y1}, {self.endX}, {self.endY}'
        return self
    
    def bezierCurveTo(self, x1: int, y1: int, x2: int, y2: int, x: int, y: int):
        self.endX = +x
        self.endY = +y
        self.str += f'C{+x1}, {+y1}, {+x2}, {+y2}, {self.endX}, {self.endY}'
        return self
    
    def horizontalEaseCurveTo(self, x: int, y: int):
        self.bezierCurveTo(self.endX * (1 - self.curve) + x * self.curve, self.endY, self.endX * self.curve + x * (1 - self.curve), y, x, y)
        return self

    def easeCurveTo(self, x: int, y: int):
        c0x = self.endX
        c0y = self.endY
        c1x = x
        c1y = y
        if ((x - self.endX)*(y - self.endY)) > 0:
            c0y = self.endY * (1 - self.curve) + y * self.curve
            c1x = self.endX * self.curve + x * (1 - self.curve)
        else:
            c0x = self.endX * (1 - self.curve) + x * self.curve
            c1y = self.endY * self.curve + y * (1 - self.curve)
        self.bezierCurveTo(c0x, c0y, c1x, c1y, x, y)
        return self

    def arc(self, x: int, y: int, radius: int, startAngle, endAngle, ccw:int=0):
        x = +x
        y = +y
        radius = +radius
        ccw = ~~ccw
        if (radius < 0): raise ValueError(f'Negative radius: {radius}')

        dx = radius * math.cos(startAngle)
        dy = radius * math.sin(startAngle)
        x0 = x + dx
        y0 = y + dy
        cw = 1^ccw
        da = endAngle - startAngle if ccw == 0 else startAngle - endAngle

        if (self.endX == None): self.str += f'M{x0}, {y0}'
        elif (abs(self.endX - x0) > epsilon or abs(self.endY - y0) > epsilon): self.str += f'L{x0}, {y0}'
        #if not radius: return

        #IMPORTANT!: discrepancy from d3.path
        # original being da = da % tau + tau, but JavaScript only updates da = da % tau in fact
        if da < 0: da = da % tau # + tau

        if (da > tauEpsilon): # this is a complete circle, so draw two arcs 
            self.endX = x0
            self.endY = y0
            self.str += f'A{radius},{radius},0,1,{cw},{x - dx},{y-dy}'
            self.str += f'A{radius},{radius},0,1,{cw},{self.endX},{self.endY}'
        elif (da > epsilon): # this is an arc, so draw it 
            self.endX = x+radius*math.cos(endAngle)
            self.endY = y+radius*math.sin(endAngle)
            self.str += f'A{radius},{radius},0,{int(da >= math.pi)},{cw},{self.endX},{self.endY}'
        return self
    
    def arcTo(self, x1: int, y1: int, x2:int, y2:int, r:int):
        x1 = +x1
        y1 = +y1
        x2 = +x2
        y2 = +y2
        r = +r

        x0 = self.endX
        y0 = self.endY
        x21 = x2 - x1
        y21 = y2 - y1
        x01 = x0 - x1
        y01 = y0 - y1
        r01 = x01 ** 2 + y01 ** 2

        if (self.endX == None): 
            self.str += f'M{x1},{y1}'
            self.endX = x1
            self.endY = y1
            return self
        elif (r01 <= epsilon): 
            return self
        elif (abs(y01 * x21 - y21 * x01) <= epsilon) or r == 0:
            self.str += f'L{x1},{y1}'
            self.endX = x1
            self.endY = y1
            return self
        
        x20 = x2 - x0
        y20 = y2 - y0
        r21 = x21**2 +y21 **2
        r20 = x20**2 + y20**2
        length = r * math.tan((math.pi - math.acos((r21 + r01 - r20)/ (2 * math.sqrt(r21) * math.sqrt(r01)))) / 2)
        t01 = length / math.sqrt(r01)
        t21 = length / math.sqrt(r21)

        if abs(t01 - 1) > epsilon: self.str += f'L{x1 + t01*x01}, {y1 + t01 * y01}'
        
        self.str += f'A{r},{r},0,0,{int(y01*x20 > x01*y20)},{x1 + t21*x21},{y1 + t21*y21}'
        self.endX = x1 + t21*x21
        self.endY = y1 + t21*y21
        return self


    def toString(self):
        return self.str

class Node():
    def __init__(self, name = '', sessionID = 0, order = 0, time = -1, index = -1):
        self.name = name
        self.id = index
        self.sessionID = sessionID
        self.timestamp = time
        self.order = order
        #TODO: add symbol information etc.
    
    def __str__(self):
        return self.name

    def getBarycenterLeaf(self, nodes):
        prevNode = self.findSelf(nodes)
        if prevNode:
            return prevNode.order
        return self.order

    # find yourself at a different timestamps
    def findSelf(self, nodes): # nodes across sessions at a different timestamp
        for each in nodes:
            if each.name == self.name:
                return each
        return None
    

class Entity():
    def __init__(self, name = '', timeline: list[Node] = [], index:int = -1):
        self.id = index
        self.name = name
        self.timeline: list[int] = timeline # sessionID?

    def setTimeline(self, timeline: list[Node]):
        self.timeline = timeline

    def getAtTimestamp(self, time: int) -> int:
        return self.timeline[time]
    
    def getBarycenterLeafAtTimestamp(self, time: int) -> int:
        pass

    def getName(self):
        return self.name


class Session():
    def __init__(self, sessionID: int = 0, 
                 entities: list[Node] = [],
                 form: str = 'contact',
                 timestamp: int = -1,
                 weight: int = 0, indices: list[int] = []):
        self.id: int = sessionID
        self.entities: list[Node] = entities # across all the timestamps
        self.entityWeight = len(entities)
        self.constraints = [] # [[dict]*5], each dict has a key being the weight, and the value being the array of the elements with the same weight
        self.type = form
        self.weight = weight
        self.indices = indices
        self.timestamp = timestamp # the index in the liner._all_timestamps
        self.hops: list[list[str]] = [] # [[top-2-hop-neighbors], [1-hop source neighbors], [ego], [1-hop target neighbors], [bottom-2-hop-neighbors]]
        self.links = []

        self.barycenter = 0

    def print_entities(self):
        return [str(entity) for entity in self.entities]

    def getIdentity(self, name):
        for idx, group in enumerate(self.hops):
            if name in group: return idx
        return -1

    def add(self, name):
        self.entities.append(name)
        self.entityWeight += 1

    def findNode(self, name, return_session=False, return_index=False):
        each: Node
        for idx, each in enumerate(self.entities):
            if each.name == name:
                if(return_session): return self
                if(return_index): return idx
                return each
        return None
    
    def set(self, hops=[], links=[], constraints=[]):
        if len(hops) != 0: self.hops = hops
        if len(links) != 0: self.links = links
        if len(constraints) != 0: self.constraints = constraints
    
    def getEntityIDs(self):
        return [node.id for node in self.entities]
    
    def replaceNode(self, nodes: list[Node], sweepRange: tuple):
        (startIdx, endIdx) = sweepRange
        for idx in range(startIdx, endIdx):
            self.entities[idx] = nodes[idx - startIdx]
        #print('replaced',[each.name for each in self.entities[startIdx:endIdx]])
            
    #to be deprecated?
    def getEntityIDsAtTimestamp(self, time) -> list[str]:
        result = []
        for each in self.entities:
            if each.timestamp != time: continue
            result.append(each.id)
        return result
    
    # These three to be deprecated
    def setHops(self, hops):
        self.hops = hops

    def setLinks(self, links):
        self.links = links
    
    def setConstraints(self, constraints):
        self.constraints = constraints

