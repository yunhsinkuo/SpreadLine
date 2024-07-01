import * as d3 from 'd3';

export class Collapser {
    constructor(block, posX, blockWidth, brushComponent) {
        this.data = block
        this.posX = posX
        this.blockWidth = blockWidth
        this.brushComponent = brushComponent
        this.duration = 500
        this.shrinkAnimation = d3.transition().duration(this.duration).ease(d3.easeQuadInOut);
        this._block_id = this.data.id
        this._moveX = this.data.moveX
    }

    act() {

        let blockWidth = this.blockWidth
        let id = this._block_id
        let moveX = this._moveX
        let animation = this.shrinkAnimation
        let posX = this.posX

        function collapseTranslate() {
            let transform = this.getAttribute('transform')
            let classes = this.getAttribute('class').split(' ')
            if (classes.includes(`points-${id}`) || classes.includes(`horizontal-bars-${id}`) || classes.includes(`button-${id}`)) return;
            if (classes.includes(`links`) || classes.includes('group')) { // do not shift any links that belong to any blocks to the left of the selected one
                let groupID = this.getAttribute('groupID')
                if (groupID < id) return;
            }
            let currX = transform.split(',')[0].split('(')[1]
            let currY = transform.split(',')[1].split(')')[0]
            let moveTo = +currX - moveX // add new width to existing translation
            if (classes.includes('rules') && this.getBBox().x < posX + blockWidth / 2) {
                moveTo = +currX - moveX / 2
            }    
            d3.select(this).transition(animation)
                .attr('transform', `translate(${moveTo}, ${+currY})`)        
        }

        let selection = d3.selectAll('.movable').filter(function () {
            let bbox = this.getBBox()
            return (bbox.x + (bbox.width / 2)) >= posX && this.getAttribute('id') !== `left-arc-${id}`
        }).each(collapseTranslate)

        let brushSelection = d3.selectAll('.brush').filter(function () {
            let groupID = this.getAttribute('groupID')
            return groupID > id
        }).each(collapseTranslate)

        let symbolSelection = d3.selectAll('.symbol-movable').filter(d => d.posX >= posX) // this is moving the triangle marks, as symbols already utilized transform to position themselves
        symbolSelection.each(function (d) { // d is data, this is the element
            let transform = this.getAttribute('transform')
            let rotate = transform.split('(')[2].split(')')[0]
            let currX = transform.split(',')[0].split('(')[1]
            d3.select(this).transition(animation)
                .attr('transform', `translate(${+currX - moveX}, ${d.posY}) rotate(${rotate})`)
        })

        this._removeDummyLines(id)
        this._collapseBlock(id)
        this._revertPointsLinks(id)
        this._updateBrush()
    }

    _revertPointsLinks(id) {
        let animation = this.shrinkAnimation
        let pointSelection = d3.selectAll(`.points-${id}`)
        pointSelection.each(function (d) {
            let transform = this.getAttribute('transform')
            let currX = transform.split(',')[0].split('(')[1]
            if (d.scaleX == 0 && d.scaleY == 0) return;
            let embX = this.getAttribute('embX')
            d3.select(this).transition(animation)
                .attr('transform', `translate(${+currX - embX}, ${0})`) 
                .attr('r', 5)
        })

        d3.selectAll(`.links-${id}`)
            .transition(animation)
            .attr('marker-end', '')
            .attrTween('stroke-dasharray', shrinkLineAnimation)
            .on('end', remove)
    
        d3.selectAll(`.brush-points-${id}`)
            .transition(animation)
            .attr('opacity', 1e-6)
            .on('end', remove)
        
        d3.selectAll(`.brush-links-${id}`)
            .transition(animation)
            .attr('marker-end', '')
            .attrTween('stroke-dasharray', shrinkLineAnimation)
            .on('end', remove) 
    }

    _collapseBlock(id) {
        d3.selectAll(`.horizontal-bars-${id}`)
            .transition(this.shrinkAnimation)
            .attrTween("stroke-dasharray", shrinkLineAnimation)

        d3.select(`#arc-group-rect-${id}`)
            .transition()
            .duration(this.duration)
            .ease(d3.easeQuadInOut)
            .attr('width', 0)
            .on('end', remove)
        
        d3.selectAll(`.board-rect-${id}`)
            .transition()
            .duration(this.duration)
            .ease(d3.easeQuadInOut)
            .attr('width', 0)
            .on('end', remove)
        
        d3.selectAll(`.board-opacity-${id}`)
            .transition()
            .duration(this.duration)
            .ease(d3.easeQuadInOut)
            .style('opacity', 1e-6)
            .on('end', remove)
    }

    _removeDummyLines(id) {
        d3.selectAll(`.dummy-movable-${id}`)
            .transition()
            .duration(this.duration)
            .ease(d3.easeQuadInOut)
            .attrTween("stroke-dasharray", shrinkLineAnimation).on('end', remove)
    }

    _updateBrush() {
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
                startX: +currX + data.posX - this.blockWidth / 2 - shiftX - expandX / 2,
                endX: +currX + data.posX + this.blockWidth / 2 - shiftX + expandX / 2,
            }
        })
        let brushMove = null
        if (this.brushComponent.brushedSelection.length != 0) {
            let [startIdx, endIdx] = this.brushComponent.brushedSelection
            let startPos = timePositions[startIdx].startX
            let endPos = timePositions[endIdx].endX
            brushMove = [startPos, endPos]
        }
        d3.select('#time-container').transition(this.shrinkAnimation).call(this.brushComponent.brush.move, brushMove)
    }

}

function remove() {
    d3.select(this).remove()
}

function shrinkLineAnimation() {
    let length = this.getTotalLength();
    return d3.interpolate(`${length},${length}`, `${0},${length}`);
}
