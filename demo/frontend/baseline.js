import * as d3 from 'd3';
import './style.css'

const response = await fetch('http://localhost:5300/fetchSpreadLine')
const ready = await response.json()

console.log(ready.resp)
const margin = { top: 100, right: 20, bottom: 20, left: 20 }

const times =["1995", "1999", "2003", "2007", "2011", "2015", "2019", "2022"]

const data = ready.resp
const ego = data.ego
const WIDTH = 600

const createStyleElementFromCSS = () => {
    // assume index.html loads only one CSS file in <header></header>
    const sheet = document.styleSheets[0];
  
    const styleRules = [];
    for (let i = 0; i < sheet.cssRules.length; i++)
      styleRules.push(sheet.cssRules.item(i).cssText);
  
    const style = document.createElement('style');
    style.type = 'text/css';
    style.appendChild(document.createTextNode(styleRules.join(' ')))
  
    return style;
  };

drawSmallMultiples()
function drawSmallMultiples() {
    let chartContainer = d3.select('#story-svg')
    chartContainer.attr('width', times.length * WIDTH + margin.left + margin.right + 100).attr('height', 700 + margin.top + margin.bottom)

    const svg = document.querySelector('svg');
    const style = createStyleElementFromCSS();
    svg.insertBefore(style, svg.firstChild);

    let blocks = data.blocks.filter(d => times.includes(d.time))
    let colors = data.storylines
    
    let labels = chartContainer.append('g')
        .selectAll()
        .data(times)
        .join('text')
        .attr('x', (d, i) => 100 + WIDTH / 2 + i * WIDTH)
        .attr('y', margin.top)
        .text(d => d)
        .style('font-size', '1rem')
        .style('font-weight', 'bold')
        .style('text-anchor', 'middle')
    
    const arrowHead = chartContainer.append("defs")
        .selectAll('marker')
        .data(['ego', 'alter'])
        .join("marker")
        .attr('id', d => `arrow-head-${d}`)
        .attr('viewBox', "0 -5 10 10")
        .attr('refX', d => (d == "ego") ? 27: 21) // 15
        .attr('refY', 0)
        .attr("markerWidth", 9)
        .attr("markerHeight", 9)
        .attr("orient", "auto")
        .attr('xoverflow','visible')
        .append('path')
        .attr('d', 'M0,-4 L10,0 L0,4 Z')
        .style('fill', '#424242')
    
    
    blocks.forEach((block, i) => { 
        let links = block.relations.map(e => ({ source: e[0], target: e[1] }))
        let authors = links.map(e => e.source)
        let points = block.points.map(e => ({
            id: e.id,
            name: e.name,
            radius: (e.name == ego) ? 15 : 10,
            color: (e.name == ego) ? "#ffffff" : colors.find(c => c.name == e.name).color,
            stroke: (authors.includes(e.id)) ? 'dashed' : 'solid'
        }))
        drawNetwork(100 + i * WIDTH, points, links)
    })

}

function drawNetwork(startX, points, links) {
    let chartContainer = d3.select('#story-svg').append('g')

    let simulation = d3.forceSimulation(points)
        .force('link', d3.forceLink(links).id(d => d.id).distance(50))
        .force('charge', d3.forceManyBody().strength(-100))
        .force('center', d3.forceCenter(startX + WIDTH / 2, 350))
        //.force('x', d3.forceX(startX + width / 2).strength(0.1))
    //.force('y', d3.forceY(350).strength(0.1))
        .force('collide', d3.forceCollide().radius(d => 10))
        .stop()

    for (let i = 0; i < 1000; i++) simulation.tick()

    console.log(links)
    const edges = chartContainer.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
        .attr('stroke', 'black')
        .attr('stroke-width', 1)
        .attr('marker-end', d => {
            if (d.target.name == ego) return `url(#arrow-head-ego)`
            return `url(#arrow-head-alter)`
        })
    
    const nodes = chartContainer.append('g')
        .selectAll('circle')
        .data(points)
        .join('circle')
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => d.radius)
        .attr('fill', d => d.color)
        .style('stroke', '#212121')
        //.style('stroke-width',  d => (d.stroke == "solid") ? 1: 2)
        //.style('stroke-dasharray', d => (d.stroke == "solid") ? '': '1,1')
}