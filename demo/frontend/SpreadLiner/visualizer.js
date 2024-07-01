import { Expander } from './expander';
import { Collapser } from './collapser';
import { arraysEqual, _compute_embedding, getTextWidth, wrap, createStyleElementFromCSS } from './helpers';

import * as d3 from 'd3';

const initConfig = {
    'legend': {
        'domain': [], 'range': [], 'offset': [],
    },
    'background': {
        'direction': [], 'directionFontSize': '', 'timeLabelFormat': (d) => d, 'timeHighlight': [],
    },
    'content': {
        'customize': () => { },
        'collisionDetection': true,
        'showLinks': true,
    },
    'tooltip': {
        'showPointTooltip': true,
        'pointTooltipContent': (name, label) => `<b>${name}</b> <br/> ${(label == -1) ? 'Unknown' : `${label}`}`,
        'showLinkTooltip': true,
    },
    'nodeColorScale': d3.scaleOrdinal().domain([]).range([]),
}

export class SpreadLinesVisualizer {
    constructor(json, config) {
        this.data = json;
        //TODO: can be replaced by lodash extend
        this.config = Object.assign({}, initConfig, config)
        this.margin = { top: 40, right: 20, bottom: 20, left: 150 };
        this.storylines = json.storylines
        this._BAND_WIDTH = json.bandWidth
        this._EGO = json.ego
        this._LEGEND_OFFSET = 40
        this._ANNOTATION_OFFSET = (this.config.background.annotations.length > 0) ? 35 : 0 //20
        this._FILTER_THRESHOLD = 1
        this._FILTER_CROSSING = false
        this._HIDE_LABELS = "some" // "reveal", "some"
        this._button_labels = {"hidden": "Hide Labels", "revealed": "Reveal Labels", "some": "Some Labels"}
        this.brushComponent = {
            brush: null,
            brushedBlocks: [],
            brushedSelection: new Array(),
        }
        this.visibility = {}
        this.members = {
            slider: [], crossing: [], pinned: [],
        }
        this.actors = {}
        //config?
        this.force = true;
        this.nodeColorScale = this.config.legend.node.scale;
    }
    
    visualize(tag) {
        let container = document.getElementById(tag.slice(1));
        let chartContainer;
        let tooltipContainer;
        if (container.tagName == 'svg') {
            chartContainer = d3.select(tag)
            let parent = chartContainer.node().parentNode
            tooltipContainer = d3.select(parent)
        } else {
            chartContainer = d3.select(tag).append('svg').attr('id', 'story-svg')
                .attr('width', '100%').attr('height', '100%')
            tooltipContainer = d3.select(tag)
        }
        let bbox = chartContainer.node().getBoundingClientRect()
        let startY = d3.max([this.margin.top, 50]) - 50
        this.brushComponent.brush = d3.brushX().extent([[0, startY], [bbox.width - this.margin.right, startY + 30 ]])
       
        console.log(this.data)

        let timeLabels = this.data.timeLabels
        let heightExtents = this.data.heightExtents
        chartContainer.attr('width', d3.max(timeLabels, d => d.posX) + this.margin.left + this.margin.right + 100)
            .attr('height', heightExtents[1] + this.margin.top + this.margin.bottom + this._LEGEND_OFFSET + this._ANNOTATION_OFFSET + 20)
        
        this.data.storylines.forEach(d => this.visibility[d.name] = true)
        
        this.chartContainer = chartContainer
        this.tooltipContainer = tooltipContainer
        let lieSpanMax = d3.extent(this.data.storylines.filter(d => d.name != this._EGO).map(d => d.lifespan))

        let storylines = this.data.storylines
        let lifeSpans = storylines.map(d => d.lifespan)
        let toShowLabel = d3.min([d3.quantile(lifeSpans, 0.8), 20])
        this.storylines = storylines.map(d => ({ ...d, label: { ...d.label, show: (d.lifespan > toShowLabel) ? 'visible' : 'hidden' } }))
        console.log(this.storylines)

        if (this.config.tooltip.showLinkTooltip || this.config.tooltip.showPointTooltip) this._createTooltip()
        this._drawBackground()
        this._activateBrush(timeLabels, this.data.blocks)
        this._drawLineLegend()
        this._drawNodeLegend()
        this._drawStorylines()
        this._drawBlocksAndPoints()
        this._drawLabels()
        this._activateFilter(lieSpanMax[1])

        //if (this._HIDE_LABELS) d3.selectAll('.line-labels, .inline-labels').filter(d => d.name != this._EGO).style('visibility', 'hidden')
        if (this._HIDE_LABELS == 'some') { 
            let ego = this._EGO
            let selection = d3.selectAll('.labels,.mark-links').filter(d => d.name !== ego).filter(d => {
                if (d.label !== undefined) {
                    return !(d.label.show == "visible")
                }
                let entity = this.storylines.find(e => e.name == d.name)
                return !(entity.label.show == 'visible')
            })
            selection.style('visibility', 'hidden')
        }

        const svg = document.querySelector('svg');
        const style = createStyleElementFromCSS();
        svg.insertBefore(style, svg.firstChild);

        const arrowHead = chartContainer.append("defs").append("marker")
            .attr('id', 'arrow-head')
            .attr('viewBox', "0 -5 10 10")
            .attr('refX', 0) // 15
            .attr('refY', 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .attr('xoverflow','visible')
            .append('path')
            .attr('d', 'M0,-4 L10,0 L0,4 Z')
            .style('fill', '#424242')
    }

    _activateFilter(lifeSpanMax) {
        let filterContainer = d3.select('#filter-container')
        let lineLegendSize = d3.select('#line-legend-container').node().getBBox()
        let nodeLegedSize = d3.select('#node-legend-container').node().getBBox()
        const filterOffset = lineLegendSize.width + 40 + nodeLegedSize.width + 40

        filterContainer.style('transform', `translate(${this.margin.left + filterOffset}px, ${d3.max([this.margin.top / 2, 20]) + 2}px)`)
        document.getElementById('length-title').innerHTML = this.config.background.sliderTitle

        const filterExecution = (group, decision) => {
            this.POINT_SELECTION(group.map(d => d.name)).classed('storyline-dehighlight', decision)
            this.MISC_SELECTION(group.map(d => d.name)).classed('storyline-dehighlight', decision)
            this.LABEL_SELECTION(group.map(d => d.name)).classed('storyline-label-dehighlight', decision)
        }

        const crossingCheck = document.getElementById('crossing')
        const lengthSlider = document.getElementById('length')
        lengthSlider.setAttribute('max', lifeSpanMax)
        
        crossingCheck.oninput = debounce(() => {
            let selected = crossingCheck.checked
            let data = this.data.storylines
            let rest = data.filter(d => (d.crossingCheck === false)).filter(d => d.name !== this._EGO).filter(d => !this.PIN_STATUS().includes(d.name))
            let keep = data.filter(d => (d.crossingCheck === true)).filter(d => d.name !== this._EGO)
            let noOthers = [...this.members.pinned]
            keep.filter(d => {
                let ele = document.getElementById(`label-${d.name}`)
                let pinned = Boolean(+ele.getAttribute('pin'))
                return (selected) ? !pinned : pinned
            }).forEach(d => this._linePin(d, 'crossing'))
            this.members.crossing = (selected) ? keep.map(d => d.name) : []
            console.log(this.members)
            if (selected == true) {
                this.ENTITY_SELECTION(keep.map(d => d.name), selected)
                filterExecution(rest.filter(e => !noOthers.includes(e)), selected)
                this.BLOCK_SELECTION(keep.map(d => d.name), 'others').filter(each => !noOthers.some(name => each.names.includes(name))).classed('storyline-arc-dehighlight', selected)
                return;
            }
            this._massHoverExecution(noOthers, 'others', (noOthers.length > 0) ? true : false)
        }, 100)
        
        lengthSlider.oninput = debounce(() => {
            let threshold = +lengthSlider.value
            document.getElementById('length-display').innerHTML = threshold
            let noOthers = [...this.members.pinned]
            let rest = this.data.storylines.filter(d => (d.lifespan < threshold)).filter(d => d.name !== this._EGO).filter(d => !this.PIN_STATUS().includes(d.name))
            let keep = this.data.storylines.filter(d => (d.lifespan >= threshold)).filter(d => d.name !== this._EGO)
            if (keep.length == this.data.storylines.length - 1) {
                keep.filter(d => this.members.slider.includes(d.name)).forEach(d => this._linePin(d, 'slider'))
            } else {
                keep.filter(d => !this.members.slider.includes(d.name)).forEach(d => this._linePin(d, 'slider'))
            }
            //console.log('newly pinned', keep.filter(d => !this.members.slider.includes(d.name)))

            //this._massHoverExecution(noOthers, 'others', (noOthers.length > 0) ? true : false)
            this.ENTITY_SELECTION(this.members.slider.filter(d => ![...keep, ...noOthers].includes(d)), false)
            this.ENTITY_SELECTION(keep.map(d => d.name), true)
            filterExecution(rest.filter(e => !noOthers.includes(e)), true)
            this.members.slider = (threshold == 1) ? [] : keep.map(d => d.name)
            if (threshold == 1) this.ENTITY_SELECTION(this._EGO, true)
            let selection = this.BLOCK_SELECTION(keep.map(d => d.name), 'others').filter(each => !noOthers.some(name => each.names.includes(name)))
            selection.classed('storyline-arc-dehighlight', true)

        }, 300)
    }

    _drawNodeLegend() {
        let legendContainer = this.chartContainer.append('g').attr('id', 'node-legend-container')

        let lineLegendSize = d3.select('#line-legend-container').node().getBBox()
        let legendTitle = this.config.legend.node.title
        //console.log(getTextWidth(legendTitle, '0.7rem'))
        const legendOffset = lineLegendSize.width + 40 + getTextWidth(legendTitle, '0.7rem bold')
        const titleOffset = 10
        const swatchSize = 10
        const swatchWidth = 3.5
        let domain = this.nodeColorScale.domain()
        let colors = [this.nodeColorScale.range(), '#ffffff'].flat()
        console.log(colors, domain)

        let legend = legendContainer.append('g').attr('transform', `translate(${this.margin.left + legendOffset}, ${d3.max([this.margin.top / 2, 20])})`)

        const title = legend.append('text').text(legendTitle).attr('transform', `translate(0, 20)`)
            .style('vertical-align', 'middle').style('font-size', '14px').style('font-weight', 'bold').style('text-anchor', 'end')
        
        const legendSwatches = legend.selectAll('rect')
            .data(colors)
            .join('rect')
            .attr('width', swatchSize * swatchWidth).attr('height', swatchSize)
            .attr('fill', d => d)
            .attr('stroke', d => (d == '#ffffff') ? '#cccccc' : '')
            .attr('stroke-width', d => (d == '#ffffff') ? 0.4 : 0)
            .attr('transform', (d, i) => (i == colors.length - 1) ? `translate(${(i+1) * swatchSize * swatchWidth + i * 1 + titleOffset}, 12)` :`translate(${i * swatchSize * swatchWidth + i * 1 + titleOffset}, 12)`)

        let offsets = [25, 65, 100, 170]
        const legendLabels = legend.selectAll('legendText')
            .data(["Negative", "Controversial", "Positive", "Neutral"])
            .join('text')
            .text(d => d)
            .attr('transform', (d, i) => `translate(${offsets[i]}, ${(i % 2 == 0) ? 7 : 10 + 25})`)
            .style('font-size', '12px')
            .style("text-anchor", "middle")
        /*const legendLabels = legend.selectAll('legendText')
            .data(domain)
            .join('text')
            .text(d => d)
            .attr('transform', (d, i) => `translate(${(i+1)*swatchSize*swatchWidth + titleOffset}, ${10 - 3})`)
            .style('font-size', '0.7rem')
            .style("text-anchor", "middle")*/

    }

    _drawLineLegend() {
        let legendContainer = this.chartContainer.append('g').attr('id', 'line-legend-container')

        let config = this.config.legend.line
        const buttonOffset = 100
        const swatchSize = 15
        const betweenOffset = [...[0], ...config.domain.map(d => getTextWidth(d, '12px') + swatchSize*2 + 5).reduce((acc, x, i) => [...acc, x + (acc[i - 1] || 0)], [])]

        let legend = legendContainer.append('g').attr('transform', `translate(${this.margin.left + buttonOffset}, ${d3.max([this.margin.top / 2, 20])})`)
        let ego = this._EGO
        let hide_status = this._HIDE_LABELS
        let statusConfig = this._button_labels
        let storylines = this.storylines


        const labelDisplayButton = legendContainer.append('g').attr('transform', `translate(${this.margin.left}, ${d3.max([this.margin.top / 2, 20]) + 10 + swatchSize / 2 + 3})`)
            .append('text')
            .text(this._button_labels[this._HIDE_LABELS])
            .attr('status', this._HIDE_LABELS)
            .style('font-size', '12px')
            .style('font-weight', 'bold')
            .style('cursor', 'pointer')
            .on('click', function (event, d) {
                let status = this.getAttribute('status')
                let lineFilter = d3.selectAll('.line-swatches').nodes().map(d => ({'status': d.getAttribute('status'), 'color': d.getAttribute('fill')}))
                if (status == 'revealed') {
                    d3.selectAll('.labels,.mark-links').filter(each => each.name != ego).style('visibility', 'hidden')
                }
                if (status == 'hidden') {
                    let selection = d3.selectAll('.labels,.mark-links').filter(d => d.name !== ego).filter(d => {
                        if (d.label !== undefined) {
                            return (d.label.show == "visible")
                        }
                        let entity = storylines.find(e => e.name == d.name)
                        //console.log(entity.label.show)
                        return (entity.label.show == 'visible')
                    })
                    //console.log(selection.nodes())  
                    selection.style('visibility', 'visible')
                    //d3.selectAll('.inline-labels').style('visibility', 'visible')
                }
                if (status == 'some') {
                    d3.selectAll('.labels,.mark-links').filter(d => d.name !== ego).style('visibility', 'visible')
                }
                let newStatus = (status == 'revealed') ? 'hidden' : (status == 'hidden') ? 'some' : 'revealed'
                console.log(hide_status, newStatus)
                hide_status = newStatus
                this.setAttribute('status', newStatus)
                this.textContent = statusConfig[newStatus]
            })
        
        const legendSwatches = legend.selectAll('rect')
            .data(config.range)
            .join('rect')
            .attr('class', 'line-swatches')
            .attr('width', swatchSize).attr('height', swatchSize)
            .attr('fill', d => d)
            .attr('status', 'revealed')
            .attr('transform', (d, i) => `translate(${betweenOffset[i]}, 10)`)
            //.style('cursor', 'pointer')
            .on('click', function (event, color) {
                let status = this.getAttribute('status')
                if (status == 'revealed') {
                    d3.selectAll('.line-filter').filter(d => d.color == color).style('visibility', 'hidden')
                    //d3.selectAll('.line-labels, .inline-labels').filter(d => d.color == color).style('visibility', 'hidden')
                    //d3.selectAll('.inline-labels').filter(d => d.name != this._EGO).style('visibility', 'hidden')
                }
                if (status == 'hidden') {
                    d3.selectAll('.line-filter').filter(d => d.color == color).style('visibility', 'visible')

                    //d3.selectAll('.line-labels, .inline-labels').filter(d => d.color == color).style('visibility', 'visible')
                    //d3.selectAll('.inline-labels').style('visibility', 'visible')
                }
                this.setAttribute('status', (status == 'revealed') ? 'hidden' : 'revealed')
                this.setAttribute('fill', (status == 'revealed') ? '#757575' : color)
            })

        const legendLabels = legend.selectAll('legendText')
            .data(config.domain)
            .join('text')
            .text(d => d)
            .attr('transform', (d, i) => `translate(${betweenOffset[i] + swatchSize+ 5}, ${10 + swatchSize / 2 + 3})`)
            .style('font-size', '12px')
            .style("text-anchor", "start")
    }

    _drawBackground() {
        let egoLabel = this.data.storylines.find(d => d.name == this._EGO).label
        let heightExtents = this.data.heightExtents
        let config = this.config.background
        let textFormat = config.timeLabelFormat
        const directionDisplay = this.chartContainer.append('g')
            .attr('id', 'direction-container')
            .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._LEGEND_OFFSET + this._ANNOTATION_OFFSET})`)
            .selectAll()
            .data(config.direction)
            .join('text')
            .text(d => d)
            .attr('class', 'text-display')
            .attr('x', this.margin.left - 50)
            .attr('y', (d, i) => (i == 0) ? egoLabel.posY - (egoLabel.posY - heightExtents[0]) * 0.5 : egoLabel.posY + (heightExtents[1] - egoLabel.posY) * 0.5)
            .attr('fill', '#c2c2c2')
            .style('opacity', .25)
            .style('font-size', config.directionFontSize)
            .style('text-anchor', 'start')
        
        const timeLabelDisplay = this.chartContainer.append('g')
            .attr('id', 'time-container')
            .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._ANNOTATION_OFFSET})`)
            .selectAll()
            .data(this.data.timeLabels)
            .join(
                enter => {
                    let container = enter.append('g')

                    let label = container.append('text')
                        .attr('class', 'movable time-labels text-display rules')
                        .attr('transform', `translate(0, 0)`)
                        .attr('id', d => `time-label-${d.label}`)
                        .text(d => textFormat(d.label))
                        .attr('x', d => d.posX)
                        .attr('y', this.margin.top / 2)
                        .attr('fill', d => {
                            let annotation = config.annotations.find(e => e.time == d.label)
                            return (annotation) ? annotation.color: '#000000'
                        })
                    
                    let rules = container.append('line')
                        .attr('class', 'movable rules')
                        .attr('transform', `translate(0, 0)`)
                        .attr('x1', d => d.posX)
                        .attr('x2', d => d.posX)
                        .attr('y1', this.margin.top / 2 + 5)
                        .attr('y2', heightExtents[1] + 20)
                        .attr('stroke', '#757575')
                        .style('opacity', 0.2)
                        .style('stroke-dasharray', ("2, 2"))

                    return container
                }
            )
        
        let wrappingLength = (this._EGO == "Benjamin Bach" | this._EGO == "Danny Masterson") ? 120 : 100
        const annotationDisplay = this.chartContainer.append('g')
            .attr('id', 'time-annotation-container')
            .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._LEGEND_OFFSET / 2})`)
            .selectAll()
            .data(config.annotations)
            .join(
                enter => {
                    let container = enter.append('g')

                    let label = container.append('text')
                        .text(d => d.text)
                        .attr('class', 'movable rules text-display')
                        .attr('x', d => {
                            let timeLabel = this.data.timeLabels.find(e => e.label == d.time)
                            return timeLabel.posX
                        })
                        .attr('y', 0)
                        .attr('transform', `translate(0, 0)`)
                        .attr('fill', d => d.color)
                        .style('font-size', '.7rem')
                        .style('text-anchor', 'middle')
                        .call(wrap, wrappingLength)
                    
                }
        )
        


    }

    _drawStorylines() {
        const storylines = this.chartContainer.append('g')
            .attr('id', 'storyline-container')
            .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._LEGEND_OFFSET + this._ANNOTATION_OFFSET})`)
            .selectAll('g')
            .data(this.data.storylines)
            .join(
                enter => {
                    let container = enter.append('g')
                        .attr('class', (d) => (d.name == this._EGO) ? 'storyline-ego' : 'storyline-alter')
                        .style('cursor', (d) => (d.name == this._EGO) ? 'default' : 'pointer')
                    
                    let line = container.append('g')
                        .attr('stroke', d => d.color)
                        .attr('name', d => d.name)
                        .attr('class', d => `line-${d.id} line-filter`)
                        .selectAll('path')
                        .data(d => d.lines)
                        .join('path')
                        .attr('d', e => e)
                        .attr('name', function() {return this.parentNode.getAttribute('name')})
                        .attr('class', d => `movable path-movable`)
                        .attr('transform', `translate(0, 0)`)
                    
                    let marks = container.append('g')
                        .attr('fill', d => d.color)
                        .attr('class', d => `line-${d.id} marks line-filter`)
                        .attr('name', d => d.name)
                        .selectAll('path')
                        .data(d => d.marks)
                        .join('path')
                        .attr('class', d => `symbol-movable`)
                        .attr('d', d3.symbol().type(d3.symbolTriangle).size(e => e.size))
                        .attr('transform', (e, idx) => (idx % 2 == 0) ? `translate(${e.posX}, ${e.posY}) rotate(90)` : `translate(${e.posX}, ${e.posY}) rotate(-90)`)
                        //.style('visibility', e => e.visibility)
                    
                    return container
                })
                .on('mouseover', this._lineHover)
                .on('click', (event, d) => this._linePin(d))
                .on('mouseout', this._lineHoverOut)
        
    }

    _drawBlocksAndPoints() {
        let nodeColorScale = this.nodeColorScale
        const blocks = this.chartContainer.append('g')
            .attr('id', 'block-container')
            .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._LEGEND_OFFSET + this._ANNOTATION_OFFSET})`)
            .selectAll('g')
            .data(this.data.blocks)
            .join(
                enter => {
                    let container = enter.append('g')
                        .attr('class', `arcs`)
                        .attr('id', (d) => `arc-group-${d.id}`)
                        .append('g')
                        .attr('id', d => `block-click-${d.id}`)
                        .on('click', this._blockUpdate)
                    
                    let leftArc = container.append('path')
                        .attr('id', d => `left-arc-${d.id}`)
                        .attr('class', d => `movable station-arcs left-arcs left-arc-${d.time}`)
                        .attr('d', d => d.outline.left)
                        .attr('transform', `translate(0, 0)`)
                        .attr('active', 0)
                    
                    let rightArc = container.append('path')
                        .attr('id', d => `right-arc-${d.id}`)
                        .attr('class', 'movable station-arcs')
                        .attr('d', d => d.outline.right)
                        .attr('transform', `translate(0, 0)`)
                    
                    container.append('path')
                        .attr('id', (d) => `top-bar-${d.id}`)
                        .attr('d', d => d.outline.top)
                        .attr('class', d => `station-arcs movable group horizontal-bars-${d.id} horizontal-bars`)
                        .attr('groupID', d => d.id)
                        .attr('transform', `translate(0, 0)`)
                        .style('visibility', 'hidden')
                    
                    container.append('path')
                        .attr('id', (d) => `bottom-bar-${d.id}`)
                        .attr('d', d => d.outline.bottom)
                        .attr('class', d => `station-arcs movable group horizontal-bars-${d.id} horizontal-bars`)
                        .attr('groupID', d => d.id)
                        .attr('transform', `translate(0, 0)`)
                        .style('visibility', 'hidden')
                    
                    let points = container
                        .selectAll('circle')
                        .data(d => d.points)
                        .join('circle')
                        .attr('class', d => `movable points-${d.group} points-${d.name} points`)
                        .attr('id', d => `point-${d.group}-${d.id}`)
                        .attr('cx', d => d.posX)
                        .attr('cy', d => d.posY)
                        .attr('r', 6)
                        .attr('fill', e => {
                            //console.log(+e.label, nodeColorScale(+e.label))
                            //return nodeColorScale(+e.label)
                            return (e.label == -100) ? '#ffffff' : nodeColorScale(+e.label)
                        })
                        .attr('transform', `translate(0, 0)`)
                        .style('visibility', d => d.visibility)
                        .style('cursor', (d) => (this.visibility[d.name] === false) ? 'default' : 'pointer')
                        .on('mouseover', (event, d) => {
                            if (this.visibility[d.name] == false) return;
                            this._showPointTooltip(d.name, +d.label)
                            this._lineHover(event, d)
                        })
                        .on('mouseout', (event, d) => {
                            if (this.visibility[d.name] == false) return;
                            d3.select('#point-tooltip').style('visibility', 'hidden')
                            this._lineHoverOut(event, d)
                        })
                })
    }

    _drawLabels() {
        let labelStatus = this._HIDE_LABELS
        const labels =this.chartContainer.append('g')
        .attr('id', 'label-container')
        .attr('transform', `translate(${this.margin.left}, ${this.margin.top + this._LEGEND_OFFSET + this._ANNOTATION_OFFSET})`)
        .selectAll('g')
        .data(this.storylines)
        .join(
            enter => {
                let container = enter.append('g')
                    .attr('class', 'pin-check')
                    .attr('name', d => d.name)
                    .attr('id', d => `label-${d.name}`)
                    .attr('point-id', d => d.id)
                    .attr('pin', 0)
                    .style('cursor', 'default')

                let label = container.append('text')
                    .attr('fill', d => d.color)
                    .text(d => d.label.label)
                    .attr('class', 'stroked-text movable text-display labels line-labels')
                    .attr('x', d => d.label.posX)
                    .attr('y', d => d.label.posY)
                    .attr('dy', '4px')
                    .attr('transform', `translate(0, 0)`)
                    .style('text-anchor', d => d.label.textAlign)
                    .style('visibility', e => e.label.visibility)
                    .on('mouseover', this._lineHover)
                    .on('mouseout', this._lineHoverOut)
            
                let inlineLabelBG = container.append('g')
                    .selectAll('text')
                    .data(d => d.inlineLabels)
                    .join('text')
                    .attr('class', 'text-display movable labels inline-labels')
                    .text(e => e.name)
                    .attr('x', e => e.posX)
                    .attr('y', e => e.posY)
                    .attr('transform', `translate(0, 0)`)
                    .style('text-anchor', 'middle')
                    .attr('stroke', '#ffffff')
                    .attr('stroke-width', '4px')
                    .attr('dy', '4px')

                let inlineLabels = container.append('g')
                    .attr('fill', d => d.color)
                    .selectAll('text')
                    .data(d => d.inlineLabels)
                    .join('text')
                    .attr('class', 'text-display stroked-text movable labels inline-labels')
                    .attr('transform', `translate(0, 0)`)
                    .text(e => e.name)
                    .attr('x', e => e.posX)
                    .attr('y', e => e.posY)
                    .style('text-anchor', 'middle')
                    .attr('dy', '4px')
                
                let labelLink = container.append('path')
                    .attr('stroke', d => d.color)
                    .attr('d', d => (d.name == this._EGO) ? "" : d.label.line)
                    .attr('name', d => d.name)
                    .style('visibility', e => e.label.visibility)
                    .attr('class', 'movable mark-links line-labels')
                    .attr('transform', `translate(0, 0)`)
                    .attr('fill', 'none')
                    .attr('stroke-width', '2px')

            })    
    }

    _blockUpdate = (event, d) => {
        let names = d.names.filter(d => d !== this._EGO)
        //if (names.map(d => this.visibility[d]).every(d => d === false)) return;
        //if (names.every(d => (this.PIN_STATUS().includes(d) === false))) return;
        let ele = document.getElementById(`left-arc-${d.id}`)
        let active = Boolean(+ele.getAttribute('active'))
        ele.setAttribute('active', +!active)
        let bbox = ele.getBBox()
        //TODO: update this to be supplement
        let supplement = {
            nodeColorScale: this.nodeColorScale,
            reference: (this.data.reference) ? this.data.reference.filter(e => e.year == d.time) : [],
        }
        let moveX = d.moveX
        let actor = active ? new Collapser(d, bbox.x, this._BAND_WIDTH, this.brushComponent)
            : new Expander(d, bbox.x, this._BAND_WIDTH, this.brushComponent, supplement, this.config.content, this._EGO)
        // So that one may still scroll through the whole visualization
        this.actors[d.id] = actor
        let currWidth = +this.chartContainer.node().getAttribute('width')
        this.chartContainer.attr('width', (active) ? currWidth - moveX : currWidth + moveX)
        actor.act();
        if (active) delete this.actors[d.id];
    };

    //Tooltip
    _createTooltip() {
        const nodeTooltip = this.tooltipContainer.append('div')
            .attr('id', 'point-tooltip')
            .attr('class', 'content-tooltip')

        this.chartContainer.on('mousemove', (event) => {
            nodeTooltip.style('top', `${event.offsetY + 15}px`).style('left', `${event.offsetX + 5}px`)
        })
    }

    _showPointTooltip = (name, label) => {
        d3.select('#point-tooltip').style('visibility', 'visible')
            .html(this.config.tooltip.pointTooltipContent(name, label))
    }

    //Hovering & Pinning
    _lineHover = (event, d) => {
        if (d.name == this._EGO) return;
        // The actual highlight
        this.LINE_SELECTION(d.id).classed('storyline-hover', true)
        if (this.GET_PIN_STATUS(d.name) == 'pinned') return;

        this.ENTITY_SELECTION(d.name, true)
        if (this.PIN_STATUS().length > 0) { // When this is triggered, that means it is dehighlighted
            this._massHoverExecution(d.name, 'target', false)
            return;
        }
        //TODO: fix this condition

        // make sure everything else is dehighlighted
        this._massHoverExecution(d.name, 'others', true)
    }

    _lineHoverOut = (event, d) => { 
        if (d.name == this._EGO) return;
        this.LINE_SELECTION(d.id).classed('storyline-hover', false)
        console.log(d.name, this.GET_PIN_STATUS(d.name))
        if (this.GET_PIN_STATUS(d.name) == 'pinned') return;
        // For others
        if (this.PIN_STATUS().length > 0) {
            this.BLOCK_SELECTION(d.name, 'target').filter(each => !this.PIN_STATUS().some(name => each.names.includes(name))).classed('storyline-arc-dehighlight', true)
            this.MISC_SELECTION(d.name, 'target').classed('storyline-dehighlight', true)
            this.POINT_SELECTION(d.name, 'target').classed('storyline-dehighlight', true)
            this.LABEL_SELECTION(d.name, 'target').classed('storyline-label-dehighlight', true)
    
            return;
        }
        // Make sure everything else goes back to normal
        this._massHoverExecution(d.name, 'others', false)
    }

    _massHoverExecution(names, group, decision) {
        this.MISC_SELECTION(names, group).classed('storyline-dehighlight', decision)
        this.POINT_SELECTION(names, group).classed('storyline-dehighlight', decision)
        this.LABEL_SELECTION(names, group).classed('storyline-label-dehighlight', decision)
        this.BLOCK_SELECTION(names, group).classed('storyline-arc-dehighlight', decision)
    }

    _linePin = (d, status='pinned') => {
        if (d.name == this._EGO) return;
        //if (this.visibility[d.name] == false) return;
        let ele = document.getElementById(`label-${d.name}`)
        let pinned = Boolean(+ele.getAttribute('pin'))
        ele.setAttribute('pin', +!pinned)
        if (status == 'pinned') {
            this.members.pinned = (pinned) ? this.members.pinned.filter(e => e !== d.name) : [...this.members.pinned, d.name]
            this.members.crossing = (pinned) ? this.members.crossing.filter(e => e !== d.name) : this.members.crossing
            this.members.slider = (pinned) ? this.members.slider.filter(e => e !== d.name) : this.members.slider
            console.log(this.members)
        }
        if (pinned) { // unpin
            this.LINE_SELECTION(d.id, 'target').classed('storyline-hover', false)
            return
        }
    }
    //Brush
    _activateBrush(timeLabels, blocks) {
        this.brushComponent.brush.on('end.snap', brushEnd)
        //let { brushedSelection, brush, brushedBlocks } = this.brushComponent
        const timeBisector = d3.bisector(d => d.currX).left
        let brusher = this.brushComponent
        let BAND_WIDTH = this._BAND_WIDTH
        let visualizer  = this

        function dblclicked() {
            const selection = d3.brushSelection(this) ? null : d3.extent(timeLabels.map(d => d.posX));
            if (selection == null) {
                d3.selectAll('.brush')
                    .transition().duration(500).ease(d3.easeQuadInOut)
                    .attr('opacity', 1e-6).on('end', function () {d3.select(this).remove()})
                brusher.brushedSelection = []
                brusher.brushedBlocks = []
                //let expandedBlockIDs = d3.selectAll('.left-arcs').nodes().filter(d => +d.getAttribute('active') == 1).map(d => d.__data__.id)
                //console.log('triggered')
                //expandedBlockIDs.forEach((id) => visualizer.actors[id].updateBrushedSelection())
            }
            d3.select(this).call(brusher.brush.move, selection);
        }
    
        function brushEnd({ selection, sourceEvent }) {
            if (!sourceEvent || !selection) return;
            let timePositions = d3.selectAll('.time-labels').nodes().map(d => {
                let data = d.__data__
                let transform = d.getAttribute('transform')
                let currX = transform.split(',')[0].split('(')[1]
                let arc = d3.select(`.left-arc-${data.label}`).node()
                let expandX = 0
                if (arc && +arc.getAttribute('active') == 1) expandX = arc.__data__.moveX
                let result = {
                    ...data, currX: +currX + data.posX,
                    startX: +currX + data.posX - expandX / 2 - BAND_WIDTH / 2, endX: +currX + data.posX + expandX / 2 + BAND_WIDTH / 2
                }
                return result
            })
            let startIdx = timeBisector(timePositions, selection[0]);
            let endIdx = timeBisector(timePositions, selection[1]) - 1;
            if (arraysEqual(brusher.brushedSelection, [startIdx, endIdx])) return;
            brusher.brushedSelection = [startIdx, endIdx]
            let startPos = timePositions[startIdx].startX
            let endPos = timePositions[endIdx].endX
            // this is date-container
            d3.select(this).transition().call(brusher.brush.move, (endPos > startPos) ? [startPos, endPos] : null)
            let timeSelection = timePositions.slice(startIdx, endIdx + 1).map(d => d.label)
            brusher.brushedBlocks = blocks.filter(d => timeSelection.includes(d.time))
            let expandedBlockIDs = d3.selectAll('.left-arcs').nodes().filter(d => +d.getAttribute('active') == 1).map(d => d.__data__.id)
            expandedBlockIDs.forEach((id) => {
                visualizer.actors[id].updateBrushedSelection()
                let brushedPointsAction = d3.selectAll(`.brush-points-${id}`)
                    .on('mouseover', (event, d) => visualizer._showPointTooltip(d.name, +d.label))
                    .on('mouseout', (event, d) => d3.select('#point-tooltip').style('visibility', 'hidden'))
            })

            //visualizer._updateBrushedSelection(expandedBlockIDs)
        } 
    
        d3.select('#time-container').call(brusher.brush).on('dblclick', dblclicked);
    }

    ENTITY_SELECTION = (names, effect) => {
        // Make sure everything related to the selection is not de-highlighted
        this.BLOCK_SELECTION(names, 'target').classed('storyline-arc-dehighlight', !effect)
        this.LABEL_SELECTION(names, 'target').classed('storyline-label-dehighlight', !effect)
        this.MISC_SELECTION(names, 'target').classed('storyline-dehighlight', !effect)
        this.POINT_SELECTION(names, 'target').classed('storyline-dehighlight', !effect)
    } 

    //Contains: marks, dummy lines, label-links, inline-labels?
    MISC_SELECTION = (names, target = 'target') => {
        let ego = this._EGO
        return (d3.selectAll(`.path-movable,.dummy-movable,.label-link-movable,.marks`).filter(function () {
            let name = this.getAttribute('name')
            return (target == 'target') ? [...[names].flat()].includes(name) : ![...[names].flat(), ego].includes(name)
        }))
    }
    BLOCK_SELECTION = (names, target = 'target') => (
        d3.selectAll('.station-arcs').filter(each => {
            let found = each.names.some(name => [...[names]].flat().includes(name))
            return (target == 'target') ? found : (!found)
        })
    )
    POINT_SELECTION = (names, target = 'target') => (
        d3.selectAll('.points').filter(each => {
            if (each.name == this._EGO) {
                let block = this.data.blocks.find(d => d.id == each.group)
                let found = block.names.some(name => [...[names]].flat().includes(name))
                let pinFound = block.names.some(name => this.PIN_STATUS().includes(name))
                return (pinFound == true) ? false : (target == 'target') ? found : !found
            }
            let found = [...[names]].flat().includes(each.name)
            return (target == 'target') ? found : !found
        })
    )
    LABEL_SELECTION = (names, target = 'target') => (
        d3.selectAll('.labels,.mark-links').filter(each => {
            let found = [...[names]].flat().includes(each.name)
            if (each.name == this._EGO) return false;
            return (target == 'target') ? found : !found
        })
    )
    LINE_SELECTION = (id) => d3.selectAll(`.line-${id}`).selectAll('*') 
    PIN_STATUS = () => Object.values(this.members).flat()
    GET_PIN_STATUS = (name) => {
        let ele = document.getElementById(`label-${name}`)
        return (Boolean(+ele.getAttribute('pin'))) ? 'pinned' : 'unpinned'
    }
    //d3.selectAll('.pin-check').nodes().filter(d => Boolean(+d.getAttribute('pin'))).map(d => d.getAttribute('name'))
}

const debounce = (callback, wait) => {
    let timeoutId = null;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => {
        callback.apply(null, args);
      }, wait);
    };
}