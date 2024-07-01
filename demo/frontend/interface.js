import { SpreadLinesVisualizer } from "./SpreadLiner/visualizer";
import { _compute_embedding, getTextWidth, wrap } from "./SpreadLiner/helpers";
import * as d3 from 'd3';
import './style.css';

//TODO: add colorscale
const cumsum = (a) => a.reduce((acc, x, i) => [...acc, x + (acc[i - 1] || 0)], [])
const getMMDD = (text) => {
    let [yyyy, mm, dd] = text.split('-')
    return `${mm}-${dd}`
}

function round(num, decimal=0) {    // Number, Number
    return +(Math.round(num + `e+${decimal}`)  + `e-${decimal}`);
}

let annotations = []
let scale = [10, 50, 100, 500]

const response = await fetch('http://localhost:5300/fetchSpreadLine')
const data = await response.json()
const ego = data.resp.ego
const reference = data.resp.reference

if (ego == 'Tamara Munzner') {
    annotations = [
        {'time': '1994', 'text': 'University of Minnesota', 'color': '#CB1B45'},
        { 'time': '1995', 'text': 'Stanford University', 'color': '#CB1B45' },
        { 'time': '2002', 'text': 'University of British Columbia', 'color': '#CB1B45' }]
}

if (ego == 'Benjamin Bach') {
    annotations = [
        { 'time': '2010', 'text': 'INRIA Joint Center', 'color': '#CB1B45' },
        { 'time': '2015', 'text': 'Microsoft', 'color': '#CB1B45' },
        { 'time': '2016', 'text': 'Monash University', 'color': '#CB1B45' },
        { 'time': '2017', 'text': 'Harvard University', 'color': '#CB1B45' },
        { 'time': '2018', 'text': 'Universtiy of Edinburgh', 'color': '#CB1B45' },
    ]
}
if (ego == 'Jeffrey Heer') {
    annotations = [
        {'time': '2002', 'text': 'Xerox Research Center', 'color': '#CB1B45'},
        { 'time': '2004', 'text': 'UC Berkeley', 'color': '#CB1B45' },
        { 'time': '2009', 'text': 'Stanford University', 'color': '#CB1B45' },
        { 'time': '2013', 'text': 'University of Washington', 'color': '#CB1B45' },
    ]
    //scale = [20, 100, 500, 1000]
}

const configuration = {
    'toy': {
        'legend': {
            'line': {
                'domain': ['Colleague', 'Collaborator'], 'range': ['#FA9902', '#146b6b'], 'offset': cumsum([0, 100])
            },
            'node': {
                'scale': d3.scaleThreshold().domain(scale).range(['#ffffff', '#fcdaca', '#e599a6', '#c94b77', '#740980']),
                    //d3.scaleLinear().domain([0, 1]).interpolate(d3.interpolateHcl).range([d3.hcl("#ffffff"), d3.hcl('#CB1B45')]),
                'title': 'Citation',
            }
        },
        'background': {
            'direction': ['', ''], 'directionFontSize': '3rem',
            'timeHighlight': [], 'timeLabelFormat':  (d) => `t${(+d) - 2014}`, 'sliderTitle': 'Days',
            "annotations": [{'time': '2017', 'text': 'Org3', 'color': '#CB1B45'}, {'time': '2015', 'text': 'Org1', 'color': '#CB1B45'}],
        },
        'content': {
            'customize':  authorContentCustomize,
            'collisionDetection': true,
            'showLinks': false,
        },
        'tooltip': {
            'showPointTooltip': true,
            'pointTooltipContent': (name, label) => `<b>${name}</b> <br/> ${label}`,
            //'showLinkTooltip': true,
            //TODO: add this
        },
    },
    'animal': {
        'legend': {
            'line': {
                'domain': ['Sow', 'Finish'], 'range': ["#E98B2A", "#507AA6"], 'offset': cumsum([0, 60]),
            },
            'node': {
                'scale': d3.scaleThreshold().domain([0, 0.5, 0.8, 1]).range(['#ffffff', '#ffd5d6', '#eb838a', '#CB1B45']),
                    //d3.scaleLinear().domain([0, 1]).interpolate(d3.interpolateHcl).range([d3.hcl("#ffffff"), d3.hcl('#CB1B45')]),
                'title': 'Unhealthy Status',
            }
        },
        'background': {
            'direction': ['Sender', 'Receiver'], 'directionFontSize': '3rem',
            'timeHighlight': ['2020-03-13'], 'timeLabelFormat': getMMDD, 'sliderTitle': 'Days',
            "annotations": [{'time': '2020-03-13', 'text': 'Outbreak', 'color': '#CB1B45'}],
        },
        'content': {
            'customize': () => { console.log('nice seal') },
            'collisionDetection': true,
            'showLinks': true,
        },
        'tooltip': {
            'showPointTooltip': true,
            'pointTooltipContent': (name, label) => `<b>${name}</b> <br/> ${(label == -1) ? 'Unknown' : `${round(label*100, 2)}%`}`,
            //'showLinkTooltip': true,
            //TODO: add this
        },
    },
    'author': {
        'legend': {
            'line': {
                'domain': ['Colleague', 'Collaborator'], 'range': ['#FA9902', '#146b6b'], 'offset': cumsum([0, 100])
            },
            'node': {
                'scale': d3.scaleThreshold().domain(scale).range(['#ffffff', '#fcdaca', '#e599a6', '#c94b77', '#740980']),
                    //d3.scaleThreshold().domain([10, 100, 500, 1500]).range(['#ffffff', '#fcdaca', '#e599a6', '#c94b77', '#740980']),
                //'scale': d3.scaleThreshold().domain([10, 50, 100, 500]).range(['#ffffff', '#ffd6d6', '#faad5a', '#fc3c2b', '#a3170a']),
                //d3.scaleThreshold().domain([50, 100, 300, 500]).range(['#ffd6ea', '#e8a9c8', '#d17ca7', '#b84e87', '#9E0F67']),
                'title': 'Citations',
            }
        },
        'background': {
            'direction': ['External', 'Internal'], 'directionFontSize': '70px', 
            'timeHighlight': '', 'timeLabelFormat': d => d, 'sliderTitle': 'Years',
            "annotations": annotations,
        },
        'content': {
            'customize': authorContentCustomize,
            'collisionDetection': true,
            'showLinks': false,
        },
        'tooltip': {
            'showPointTooltip': true,
            'pointTooltipContent': (name, label) => `<b>${name}</b> <br/> ${(label == -1) ? 'Unknown' : `${label}`}`,
        },
    },
    'metoo': {
        'legend': {
            'line': {
                'domain': ['People', 'Generic', 'Fact', 'Opinion'],
                'range': ['#cc7914', '#63360f', '#518254', '#87b043'],
                'offset': cumsum([0, 160, 100, 170, 120]),
            },
            'node': {
                'scale':
                    d3.scaleThreshold().domain([-0.3, 0.3]).range(['#DA9EB8', '#FFE2B9','#9189B4']),

                    //d3.scaleThreshold().domain([-0.7, -0.3, 0.3, 0.7]).range(['#cf4938', '#e1afa3', '#9325b8','#b3b4d7', '#3160bd']),
                    //d3.scaleOrdinal().domain([-1]).range(['#edf8e9', '#bae4b3', '#74c476', '#31a354', '#006d2c']),
                'title': 'Attitude',
            }
        },
        'background': {
            'direction': ['Oppose/Neutral', 'Support'], 'directionFontSize': '90px',
            'timeHighlight': ['2023-09-07'], 'timeLabelFormat': getMMDD, 'sliderTitle': 'Days',
            "annotations": [{ 'time': '2023-09-07', 'text': 'Sentence', 'color': '#CB1B45' },
                { 'time': '2023-09-10', 'text': 'Apology from Ashton and Mila', 'color': '#CB1B45' },
                { 'time': '2023-09-16', 'text': 'Russell Brand exposed', 'color': '#CB1B45' },
                { 'time': '2023-09-19', 'text': 'Divorce', 'color': '#CB1B45' }],
        },
        'content': {
            'customize': metooKnowledgeCustomize,
            'collisionDetection': true,
            'showLinks': true,
        },
        'tooltip': {
            'showPointTooltip': true,
            'pointTooltipContent': (name, label) => `<b>${name}</b> <br/> ${(label == -100) ? 'Unknown' : `${label}`}`,
        }
    },
}


function authorContentCustomize(container, supplement, bbox, moveX, currX, id, topPosY, posX, strokeWidth, animation) {
    let references = supplement.reference.map((d,i) => {
        let toBeX = _compute_embedding(d.posX, moveX)
        let textWidth = getTextWidth(d.name, '0.4rem')
        //console.log(toBeX, currX, textWidth / 2, textWidth, moveX, d.name)
        let wrapWidth = ((toBeX - currX) < textWidth / 2) ? 0.2 :  0.4
        return ({...d, wrapWidth: wrapWidth, id: i})
    })
    let texts = container.selectAll('text')
        .data(references)
        .join('text')
        .attr('class', `movable group board-opacity-${id}`)
        .attr('groupID', id)
        .attr('x', posX)
        .attr('y', d => _compute_embedding(d.posY, moveX))
        //.attr('dy', '-5px')
        .text(d => d.name)
        .attr('font-size', '.5rem')
        .style('text-anchor', 'middle')
        .attr('transform', d => `translate(${+currX + _compute_embedding(d.posX, moveX)} , ${topPosY})`)
        .call(wrap, moveX)
        .on('mouseover', function (event, d) {
            d3.select(this).style('fill', '#CB1B45').classed('stroked-text', true).style('font-weight', 'bold').raise()
            //d3.select(`#bg-label-${id}-${d.id}`).style('visibility', 'visible')
        })
        .on('mouseout', function(event, d){
            d3.select(this).style('fill', '#000000').classed('stroked-text', false).style('font-weight', 'normal')
            //d3.select(`#bg-label-${id}-${d.id}`).style('visibility', 'hidden')
            d3.selectAll(`.points-${id}`).raise()
        })
    //.raise()

}

function metooKnowledgeCustomize(container, supplement, bbox, moveX, currX, id, topPosY, posX, strokeWidth, animation){
    let block = data.resp.blocks.find(d => d.id == id)
    let points = block.points
    let time = block.time
    let links = reference.filter(d => d.time == time)
    let labels = links.map(d => {
        let source = points.find(p => p.name == d.source)
        let target = points.find(p => p.name == d.target)
        console.log(source, target)
        let sourceX = _compute_embedding(source.scaleX, moveX)
        let targetX = _compute_embedding(target.scaleX, moveX)
        let sourceY = _compute_embedding(source.scaleY, moveX)
        let targetY = _compute_embedding(target.scaleY, moveX)
        //console.log(0.5*(sourceX + targetX), 0.5*(sourceY + targetY))
        return { label: d.Context, posX: 0.5*(sourceX + targetX), posY: 0.5*(sourceY + targetY), rotate: Math.atan2(sourceY-targetY, sourceX-targetX) * 180 / Math.PI }
    })
    let texts = container.selectAll('text')
        .data(labels)
        .join('text')
        .attr('class', `movable group board-opacity-${id} stroked-text relation-labels`)
        .attr('groupID', id)
        .attr('x', posX)
        .attr('y', d => d.posY)
        //.attr('dy', '-5px')
        .text(d => d.label)
        .attr('font-size', '14px')
        .style('text-anchor', 'middle')
        .attr('dy', '5px')
        .attr('dx', '20px')
        .attr('transform', d => `translate(${+currX + d.posX} , ${topPosY})`)
        //.style('font-weight', 'bold')
        .style('z-index', 1)
        //.call(wrap, moveX)
        .on('mouseover', function (event, d) {
            d3.select(this).style('fill', '#CB1B45').raise()
            d3.selectAll('.relation-labels').raise()
            //d3.select(`#bg-label-${id}-${d.id}`).style('visibility', 'visible')
        })
        .on('mouseout', function(event, d){
            d3.select(this).style('fill', '#000000')
            //d3.select(`#bg-label-${id}-${d.id}`).style('visibility', 'hidden')
            d3.selectAll(`.points-${id}`).raise()
        })
    
    let targets = ['Danny Masterson', 'Russell Brand', 'Predator']
    //let targets = ['Danny Masterson', 'Apology', 'Survivor', 'Ashton Kutcher', 'Mila Kunis']
    //let targets = ['Verbal evidence', 'Danny Masterson', 'Sentence', 'No physical evidence', '30 years in prison']
    let annotation = points.filter(d => targets.includes(d.name))
    let nodeTexts = container.selectAll('peopleText')
        .data(annotation)
        .join('text')
        .attr('class', `movable group board-opacity-${id} stroked-text people-labels`)
        .attr('groupID', id)
        .attr('x', d => posX)
        .attr('y', d => _compute_embedding(d.scaleY, moveX))
        .attr('dx', '.5rem')
        .attr('dy', '.5rem')
        .text(d => d.name)
        .attr('font-size', '16px')
        .style('text-anchor', 'start')

        .attr('transform', d => `translate(${+currX + _compute_embedding(d.scaleX, moveX)} , ${topPosY})`)
        //.style('font-weight', 'bold')
        .call(wrap, moveX)
    
    
}


const visualizer = new SpreadLinesVisualizer(data.resp, configuration[data.resp.mode]);
visualizer.visualize('#story-svg');