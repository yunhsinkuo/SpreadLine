import * as d3 from 'd3'
import { _compute_embedding, _compute_elliptical_arc } from './helpers'

// Force simulation reference: https://observablehq.com/@ben-tanen/a-tutorial-to-using-d3-force-from-someone-who-just-learned-ho

export class Expander {
    constructor(block, posX, bandWidth, brushComponent, supplement, config, ego) {
        this.data = block
        this.posX = posX
        this.blockWidth = bandWidth
        this.brushComponent = brushComponent
        this.supplement = supplement
        this.duration = 500
        this.ego = ego
        this.growAnimation = d3.transition().duration(this.duration).ease(d3.easeQuadInOut);
        this.existence = {points: [], relations: []}
        this._top_posY = this.data.topPosY
        this._block_id = this.data.id
        this._moveX = this.data.moveX
        this._nodeColorScale = this.supplement.nodeColorScale
        this.linkColor = '#424242'

        this.force = config.collisionDetection
        this.forceMode = 'circle'
        this.drawLinks = config.showLinks
        this.customizeComponent = config.customize
    }

    act() {
        let blockWidth = this.blockWidth
        let animation = this.growAnimation
        let id = this._block_id
        let posX = this.posX
        let moveX = this._moveX
        function expandTranslate() {
            let transform = this.getAttribute('transform')
            let classes = this.getAttribute('class').split(' ')
            if (classes.includes(`points-${id}`) || classes.includes(`horizontal-bars-${id}`) || classes.includes(`button-${id}`)) return;
            if (classes.includes(`links`) || classes.includes('group')) { // do not shift any links that belong to any blocks to the left of the selected one
                let groupID = this.getAttribute('groupID')
                if (groupID < id) return;
            }
            let currX = transform.split(',')[0].split('(')[1]
            let currY = transform.split(',')[1].split(')')[0]
            let moveTo = +currX + moveX // add new width to existing translation
            if (classes.includes('rules') && this.getBBox().x < posX + blockWidth / 2) {
                moveTo = +currX + moveX / 2
            }
            d3.select(this).transition(animation)
                .attr('transform', `translate(${moveTo}, ${+currY})`)
        }

        // Shifting most elements to the right
        let selection = d3.selectAll('.movable').filter(function () {
            let bbox = this.getBBox()
            return (bbox.x + (bbox.width / 2)) >= posX && this.getAttribute('id') !== `left-arc-${id}`
        }).each(expandTranslate)

        let brushSelection = d3.selectAll('.brush').filter(function () {
            let groupID = this.getAttribute('groupID')
            return groupID > id
        }).each(expandTranslate)

        let symbolSelection = d3.selectAll('.symbol-movable').filter(d => d.posX >= posX) // this is moving the triangle marks, as symbols already utilized transform to position themselves
        symbolSelection.each(function (d) { // d is data, this is the element
            let transform = this.getAttribute('transform')
            let rotate = transform.split('(')[2].split(')')[0]
            let currX = transform.split(',')[0].split('(')[1]
            d3.select(this).transition(animation)
                .attr('transform', `translate(${+currX + moveX}, ${d.posY}) rotate(${rotate})`)
        })
        
        this._fillDummyLines(id)
        this._expandBlock(id)
        this._contextualize(id)
        this._updateBrush()
    }

    _contextualize(id) {
        let length = this._moveX
        let animation = this.growAnimation
        let baseline = this._top_posY
        let ego = this.ego
        let pointSelection = d3.selectAll(`.points-${id}`)
        let nodes = pointSelection.data().map(d => ({
            name: d.name, id: d.id, posX: d.posX, posY: d.posY, group: d.group, label: d.label,
            x: _compute_embedding(d.scaleX, length), y: _compute_embedding(d.scaleY, length),
            width: (d.name == ego) ? 10 : 6, height: (d.name == ego) ? 10 : 6,
        }))
        if (this.force && this.forceMode == 'circle') {
            let simulation = d3.forceSimulation(nodes)
                .force('x', d3.forceX(d => d.x))
                .force('y', d3.forceY(d => d.y))
                .force('collide', d3.forceCollide(d => d.width)) // the radius of the circle, with one additional radius for space
                .stop()
            for (let i = 0; i < 100; i++) simulation.tick()
        }
        pointSelection.each(function (d, idx) {
            let transform = this.getAttribute('transform')
            let currX = transform.split(',')[0].split('(')[1]
            if (d.scaleX == 0 && d.scaleY == 0) return;
            let node = nodes[idx]
            d3.select(this).attr('embX', node.x)
            d3.select(this).transition(animation)
                .attr('transform', `translate(${+currX + node.x}, ${-d.posY + baseline + node.y})`)
            if (d.name == ego) d3.select(this).attr('r', 7)
        })
        this.existence.points = nodes

        if (this.drawLinks) this._drawLinks(nodes)
    }

    _drawLinks(nodes) {
        let id = this._block_id
        let relations = this.data.relations
        let baseline = this._top_posY
        let ego = this.ego
        let relationArcs = relations.map(([sourceID, targetID]) => {
            let source = nodes.find(d => d.id == sourceID)
            let target = nodes.find(d => d.id == targetID)
            let sourceCoordinate = [source.x + source.posX, source.y + baseline]
            let targetCoordinate = [target.x + target.posX, target.y + baseline]
            let sourceRadius = (source.name == ego) ? 7 : 5
            let targetRadius = (target.name == ego) ? 7 : 5
            let arc = _compute_elliptical_arc(sourceCoordinate, targetCoordinate, sourceRadius, targetRadius)
            let ele = d3.select(`#point-${id}-${sourceID}`).node()
            let transform = ele.getAttribute('transform')
            let currX = +transform.split(',')[0].split('(')[1]
            return {'relation': arc, 'currX': currX}
        })

        let container = d3.select(`#block-click-${id}`)
        if (d3.selectAll(`.link-group-${id}`).nodes().length > 0) d3.selectAll(`.link-group-${id}`).remove()
        
        container.append('g') // this is needed to avoid selecting other unwanted arcs
            .attr('class', `link-group-${id}`)
            .selectAll('path')
            .data(relationArcs)
            .join('path')
            .attr('class', `movable links-${id} links`)
            .attr('id', (e, idx) => `arc-${idx}`)
            .attr('transform',d => `translate(${d.currX}, 0)`)
            .attr('fill', 'none')
            .attr('stroke', this.linkColor)
            .attr('groupID', id)
            .attr('d', (e) => e.relation)
            .transition(this.growAnimation)
            .attrTween('stroke-dasharray', growLineAnimation)
            .on('end', function () { d3.select(this).attr('marker-end', 'url(#arrow-head)') })
        
        this.existence.relations = relations
    }

    _expandBlock(id) {
        let button = this.data.outline.button
        let burhsedBlocks = this.brushComponent.brushedBlocks
        let moveX = this._moveX
        let animation = this.growAnimation

        let container = d3.select(`#block-click-${id}`)
        
        d3.selectAll(`.horizontal-bars-${id}`)
            .style('visibility', 'visible')
            .transition(animation)
            .attrTween("stroke-dasharray", growLineAnimation)
    
        let ele = document.getElementById(`right-arc-${id}`)
        let bbox = ele.getBBox()
        let strokeWidth = parseInt(getComputedStyle(ele).getPropertyValue('stroke-width'))
        let transform = ele.getAttribute('transform')
        let currX = transform.split(',')[0].split('(')[1]

        const canvas = container.append('rect')
            .attr('id', `arc-group-rect-${id}`)
            .attr('class', 'movable group')
            .attr('groupID', id)
            .attr('x', bbox.x)
            .attr('y', bbox.y + strokeWidth / 2)
            .attr('height', bbox.height - strokeWidth)
            .attr('fill', '#ffffff')
            .attr('transform', `translate(${+currX}, 0)`)
            .style('cursor', 'pointer')
            .transition(animation)
            .attr('width', moveX + 1)
            .on('end', () => this.updateBrushedSelection())

        //TODO: Create the button??

        this.customizeComponent(container, this.supplement, bbox, moveX, currX, id, this._top_posY, this.posX, strokeWidth, animation)
        d3.selectAll(`.points-${id}`).raise()
    }

    _updateBrush() {
        // Retrieve the corresponding time label of the selected block, done by bisect
        let timeLabels = d3.selectAll('.time-labels')
    
        let time = this.data.time
        let index = timeLabels.data().findIndex(d => d.label == time)
        let timePositions = timeLabels.nodes().map((d, idx) => {
            let data = d.__data__
            let transform = d.getAttribute('transform')
            let currX = transform.split(',')[0].split('(')[1]
            let arc = d3.select(`.left-arc-${data.label}`).node()
            let expandX = 0
            if (arc && +arc.getAttribute('active') == 1) expandX = arc.__data__.moveX
            let shiftX = (idx == index) ? this._moveX / 2 : (idx > index) ? this._moveX : 0
            return {
                startX: +currX + data.posX - this.blockWidth / 2 + shiftX - expandX / 2,
                endX: +currX + data.posX + this.blockWidth / 2 + shiftX + expandX / 2,
            }
        })
        let brushMove = null
        if (this.brushComponent.brushedSelection.length != 0) {
            let [startIdx, endIdx] = this.brushComponent.brushedSelection
            let startPos = timePositions[startIdx].startX
            let endPos = timePositions[endIdx].endX
            brushMove = [startPos, endPos]
        }
        d3.select('#time-container').transition(this.growAnimation).call(this.brushComponent.brush.move, brushMove)
    }

    _fillDummyLines(id) {
        let posX = this.posX
        let names = this.data.names
        let animation = this.growAnimation
        let moveX = this._moveX
        // For all the line segments that will get shifted, we find those that are next to the selected block
        let lineSelection = d3.selectAll('.path-movable').filter(function () {
            let bbox = this.getBBox() // the first M points would be x and y in bbox
            let name = this.parentNode.getAttribute('name')
            return +(bbox.x).toFixed(3) == +(posX.toFixed(3)) && !names.includes(name)
        })
        // fill in the dummy line segments
        lineSelection.each(function (d) {
            let startM = this.getAttribute('d').split(' ')[0].split(',')
            let startX = +startM[0].slice(1)
            let startY = +startM[1]
            let parentContainer = d3.select(this.parentNode)
            let transform = this.getAttribute('transform')
            let currX = transform.split(',')[0].split('(')[1]
            
            let name = this.getAttribute('name')
            parentContainer.append('path')
                .attr('d', `M${startX},${startY} L${startX + moveX},${startY}`)
                .attr('class', `movable dummy-movable-${id} dummy-movable`)
                .attr('transform', `translate(${+currX}, 0)`)
                .attr('name', name)
                .transition(animation)
                .attrTween("stroke-dasharray", growLineAnimation)
        })
    }

    _removeBrushedElements(id) {
        // For some reason it has to be there, otherwise the deletion of the circle element would complain
        const animation = d3.transition().duration(500).ease(d3.easeQuadInOut);

        let currentSelection = d3.selectAll(`.brush-${id}`)
        let toBeRemoved = currentSelection.filter(each => !this.brushComponent.brushedBlocks.map(d => d.id).includes(each.group))
        let removedPoints = []
        let removedRelations = []
        toBeRemoved.each(function (each) {
            if (this.tagName == 'path') {
                d3.select(this).transition(animation).attr('marker-end', '')
                    .attrTween('stroke-dasharray', shrinkLineAnimation).on('end', remove)
                removedRelations.push(each)
            }
            if (this.tagName == 'circle') {
                d3.select(this).transition(animation).attr('opacity', 1e-6).on('end', remove)
                removedPoints.push(each)
            }
        })

        d3.selectAll(`.brush-group-${this._block_id}`).each(function (each) {
            if (d3.select(this).selectAll('*').nodes().length == 0) {
                d3.select(this).remove()
            }
        })
        return { points: removedPoints, relations: removedRelations}
    }

    _drawBrushedPoints(container, fixedBrushPoints, newPoints) {
        let mainPoints = this.existence.points
        let arc = d3.select(`#left-arc-${this._block_id}`).node()
        let baseX = arc.getBBox().x + arc.getBBox().width
        let transform = arc.getAttribute('transform')
        let currX = transform.split(',')[0].split('(')[1]

        let nodes = [...mainPoints.map(d => ({ ...d, fx: d.x, fy: d.y })), ...fixedBrushPoints.map(d => ({ ...d, fx: d.x, fy: d.y })), ...newPoints]
        if (this.force) {
            let simulation = d3.forceSimulation(nodes)
                .force('x', d3.forceX(d => d.x))
                .force('y', d3.forceY(d => d.y))
                .force('collide', d3.forceCollide(5+1)) // the radius of the circle
                .stop()
            for (let i = 0; i < 100; i++) simulation.tick()
        }
        //console.log('after', nodes, newPoints)
        let addedBrushPoints = container.selectAll('circle')
            .data(newPoints)
            .join('circle')
            .attr('class', `points brush-${this._block_id} brush brush-points-${this._block_id}`)
            .attr('groupID', this._block_id)
            .attr('cx', baseX)
            .attr('cy', this._top_posY)
            .attr('r', 5)
            .attr('fill', e => this._nodeColorScale(e.label))
            .attr('transform', d => `translate(${+currX + d.x}, ${d.y})`)
    }

    //NOTE: current decision: don't need to add links, because you can just open small multiples
    //TODO: remove the prepping code that add links
    //TODO: allow the dynamic positioning of the nodes to be drawn
    updateBrushedSelection() {
        //this existing carries over, annoying
        let existing = { points: this.existence.points, relations: this.existence.relations }
        let existingPointLength = existing.points.length
        let existingRelationLength = existing.relations.length
        let fixedBrushPoints = []

        // Remove those that are not in the selection anymore
        let removal = this._removeBrushedElements(this._block_id)

        let currentBrushedPoints = d3.selectAll(`.brush-points-${this._block_id}`).filter(each => !removal.points.includes(each))
        let currentBrushedRelations = d3.selectAll(`.brush-links-${this._block_id}`) 
        if (currentBrushedPoints.nodes().length != 0) {
            fixedBrushPoints = currentBrushedPoints.data()
            existing.points = [...existing.points, ...currentBrushedPoints.data()]
            existingPointLength += currentBrushedPoints.nodes().length
        }

        const relationExists = (each, array) => array.some((ele) => arraysEqual(ele.relation, each))
        let container = d3.select(`#block-click-${this._block_id}`).append('g')
            .attr('class', `brush-group-${this._block_id}`)
            .attr('opacity', 0.4)
        

        this.brushComponent.brushedBlocks.filter(e => e.id != this._block_id).forEach((block) => { 
            let existingNames = existing.points.map(each => each.name)
            let uniquePoints = block.points.filter(each => !existingNames.includes(each.name))
            existing.points = [...existing.points, ...uniquePoints]
        })

        let tobeAdded = {
            points: existing.points.slice(existingPointLength).map(d => ({
                name: d.name, id: d.id, posX: d.posX, posY: d.posY, group: d.group, label: d.label,
                x: _compute_embedding(d.scaleX, this._moveX), y: _compute_embedding(d.scaleY, this._moveX)    
            })), relations: []
        }
        if (tobeAdded.points.length == 0) return;
        this._drawBrushedPoints(container, fixedBrushPoints, tobeAdded.points)
    }
}

function growLineAnimation() {
    let length = this.getTotalLength();
    return d3.interpolate(`0,${length}`, `${length},${length}`);
}

function shrinkLineAnimation() {
    let length = this.getTotalLength();
    return d3.interpolate(`${length},${length}`, `${0},${length}`);
}
function remove() {
    d3.select(this).remove()
}