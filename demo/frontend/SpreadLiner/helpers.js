import * as d3 from 'd3';
export function convertRemToPixels(rem) {    
    return rem * parseFloat(getComputedStyle(document.documentElement).fontSize);
}

export const createStyleElementFromCSS = () => {
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

export function wrap(text, width) {
    text.each(function (d) {
        let wrapping = d.wrapWidth || 1
        var text = d3.select(this),
            words = text.text().split(/\s+/).reverse(),
            word,
            line = [],
            lineNumber = 0,
            lineHeight = 1.1, // ems
            x = text.attr("x"),
            y = text.attr("y"),
            dy = 0, //parseFloat(text.attr("dy")),
            tspan = text.text(null)
                        .append("tspan")
                        .attr("x", x)
                        .attr("y", y)
                        .attr("dy", dy + "em");
        while (word = words.pop()) {
            line.push(word);
            tspan.text(line.join(" "));
            if (tspan.node().getComputedTextLength() > width * wrapping) {
                line.pop();
                tspan.text(line.join(" "));
                line = [word];
                tspan = text.append("tspan")
                            .attr("x", x)
                            .attr("y", y)
                            .attr("dy", ++lineNumber * lineHeight + dy + "em")
                            .text(word);
            }
        }
    });
}

/**
* Uses canvas.measureText to compute and return the width of the given text of given font in pixels.
* 
* @param text The text to be rendered.
* @param {String} font The css font descriptor that text is to be rendered with (e.g. "14px verdana").
* 
* @see http://stackoverflow.com/questions/118241/calculate-text-width-with-javascript/21015393#21015393
*/
export function getTextWidth(text, font) {
   // if given, use cached canvas for better performance
   // else, create new canvas
   var canvas = getTextWidth.canvas || (getTextWidth.canvas = document.createElement("canvas"));
   var context = canvas.getContext("2d");
   context.font = font;
   var metrics = context.measureText(text);
   return metrics.width;
};

export function arraysEqual(a, b) {
    if (a === b) return true;
    if (a == null || b == null) return false;
    if (a.length !== b.length) return false;
  
    // If you don't care about the order of the elements inside
    // the array, you should sort both arrays here.
    // Please note that calling sort on an array will modify that array.
    // you might want to clone your array first.
  
    for (var i = 0; i < a.length; ++i) {
      if (a[i] !== b[i]) return false;
    }
    return true;
}

export function _compute_embedding(scale, length) {
    let whiteSpace = 0.15
    return (scale + whiteSpace / 2) * length * (1 - whiteSpace)
}

export function _compute_bezier_line(start, end) {
    let midX = 0.5 * (start[0] + end[0])
    let control1 = [midX, start[1]]
    let control2 = [midX, end[1]]
    return [control1, control2]
}

function _determine_farther_factor(start, end) {
    let [x1, y1] = start
    let [x2, y2] = end
    let dy = y2 - y1
    let dx = x2 - x1
    let dr = Math.sqrt(dy ** 2 + dx ** 2)
    //console.log(dr)
    //return 0 
    return (dr > 38) ? 0.2 : (dr > 26) ? 0.5 : (dr > 13) ? 0.3 : 1.0
}
//Improvements:
// https://stackoverflow.com/questions/41226734/align-marker-on-node-edges-d3-force-layout/41229068#41229068

//Reference:
// https://stackoverflow.com/questions/46593199/elliptical-arc-arrow-edge-d3-forced-layout
export function _compute_elliptical_arc(start, end, startRadius=5, endRadius=7) {
    let arc = d3.path()
    let [x1, y1] = start
    let [x2, y2] = end
    let dy = y2 - y1
    let dx = x2 - x1
    let dr = Math.sqrt(dy ** 2 + dx ** 2)
    dy = dy / dr
    dx = dx / dr

    let mx = (x1 + x2) * 0.5
    let my = (y1 + y2) * 0.5

    let farther = _determine_farther_factor(start, end)

    let factor = farther * dr
    let cx = mx + dy * factor
    let cy = my - dx * factor

    let r = ((x1 - cx) ** 2 + (y1 - cy) ** 2) / factor * 0.5
    let rx = cx - dy * r
    let ry = cy + dx * r

    r = Math.abs(r)
    let a1 = Math.atan2(y1 - ry, x1 - rx)
    let a2 = Math.atan2(y2 - ry, x2 - rx)
    a1 = (a1 + Math.PI * 2) % (Math.PI * 2)
    a2 = (a2 + Math.PI * 2) % (Math.PI * 2)
    
    if (farther < 0 && a1 < a2) a1 += Math.PI * 2
    else if (farther >= 0 && a1 > a2) a2 += Math.PI * 2

    let arrowSize = 7
    let arrowAngle = arrowSize / r * Math.sign(farther)

    a1 += startRadius / r * Math.sign(farther)
    a2 -= endRadius / r * Math.sign(farther)
    let aa1 = a1
    let aa2 = a2 - arrowAngle * 0.7

    if ((farther < 0 && aa1 < aa2) || (farther > 0 && aa2 < aa1)) {
        aa1 = a1
        aa2 = a2
    }

    if (farther == 0) {
        arc.moveTo(x1 + dx*startRadius, y1 + dy*startRadius)
        arc.lineTo(x2 - dx*endRadius - 5*dx, y2 - dy*endRadius - 5*dy)
        return arc.toString()
    }

    arc.arc(rx, ry, r, aa1, aa2, +(farther < 0))
    return arc.toString()
}