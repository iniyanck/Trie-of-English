const width = window.innerWidth;
const height = window.innerHeight;

const svg = d3.select("#graph-container")
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .call(d3.zoom().on("zoom", function ({ transform }) {
        g.attr("transform", transform);
    }));

const g = svg.append("g");

const linkGroup = g.append("g").attr("class", "links");
const nodeGroup = g.append("g").attr("class", "nodes");

// UI Elements
const uiContainer = d3.select("#ui-container");
const nodeInfoDisplay = d3.select("#node-info-display");
const genBtn = d3.select("#gen-btn");
const wordList = d3.select("#word-list");
const themeToggle = document.getElementById("theme-toggle");

// Initially hidden
uiContainer.classed("visible", false);

let graphNodes = [];
let graphLinks = [];
let simulation;

// --- STATE VARIABLES ---
let isGraphFrozen = false;
let frozenNodeId = null;
let isDarkMode = true;

// --- ICONS (SVG) ---
const moonIcon = `<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
const sunIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="6" fill="currentColor" stroke="none"></circle><line x1="12" y1="2" x2="12" y2="5"></line><line x1="12" y1="19" x2="12" y2="22"></line><line x1="2" y1="12" x2="5" y2="12"></line><line x1="19" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="4.93" x2="7.07" y2="7.07"></line><line x1="16.93" y1="16.93" x2="19.07" y2="19.07"></line><line x1="4.93" y1="19.07" x2="7.07" y2="16.93"></line><line x1="16.93" y1="7.07" x2="19.07" y2="4.93"></line></svg>`;

// Initialize Icon
themeToggle.innerHTML = moonIcon;

// --- THEME LOGIC ---
themeToggle.addEventListener("click", () => {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle("dark-mode", isDarkMode);
    themeToggle.innerHTML = isDarkMode ? sunIcon : moonIcon;
    
    // Re-render styles that D3 might have set directly (though mostly handled via CSS class)
    if(isGraphFrozen) {
        // Force a minor update to ensure color variables apply if currently highlighted
        d3.selectAll('.node').style('stroke', null).style('fill', null);
    }
});

// --- CONFIGURATION ---
const SUBGRAPH_CONFIG = {
    verticalSpacing: 60,
    horizontalSpacing: 40,
    transitionDuration: 500,
    focusStrength: 0.9 
};

d3.json(`../lattice_trie_graph.json?t=${new Date().getTime()}`).then(graph => {
    graphNodes = graph.nodes;
    graphLinks = graph.links;

    // --- Layout Logic ---
    const maxLevel = d3.max(graph.nodes, d => d.level);
    const levelToY = d3.scaleLinear()
        .domain([0, maxLevel])
        .range([height * 0.1, height * 0.9]);

    const nodesByLevel = d3.group(graph.nodes, d => d.level);

    nodesByLevel.forEach((nodes, level) => {
        const numNodesOnLevel = nodes.length;
        const startX = (width - (numNodesOnLevel - 1) * 50) / 2;
        nodes.sort((a, b) => a.id - b.id);
        nodes.forEach((node, i) => {
            node.fx = startX + i * 50;
            node.fy = levelToY(level);
            node.originalFx = node.fx;
            node.originalFy = node.fy;
            node.x = node.fx;
            node.y = node.fy;
        });
    });

    simulation = d3.forceSimulation(graph.nodes)
        .force("link", d3.forceLink(graph.links).id(d => d.id).distance(100))
        .on("tick", ticked);

    // --- Elements ---
    const link = linkGroup
        .selectAll("line")
        .data(graph.links)
        .join("line")
        .attr("class", "link");

    const node = nodeGroup
        .selectAll("circle")
        .data(graph.nodes)
        .join("circle")
        .attr("r", 10)
        .attr("class", d => {
            let classes = `node`;
            if (d.name === 'ROOT') classes += ' root';
            if (d.name === 'END') classes += ' sink-end-node';
            return classes;
        })
        .on("click", handleNodeClick);

    const nodeLabel = nodeGroup
        .selectAll("text")
        .data(graph.nodes)
        .join("text")
        .attr("class", "node-label")
        .attr("dy", "0.35em")
        .text(d => (d.name === 'ROOT' || d.name === 'END') ? '' : d.name);

    function ticked() {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("cx", d => d.x)
            .attr("cy", d => d.y);

        nodeLabel
            .attr("x", d => d.x)
            .attr("y", d => d.y);
    }

    // --- Word Generation Logic ---
    genBtn.on("click", () => {
        if (!frozenNodeId) return;
        const centerNode = graphNodes.find(n => n.id === frozenNodeId);
        if (!centerNode) return;
        
        generateWords(centerNode);
    });

    function generateWords(centerNode) {
        wordList.html(""); // Clear previous

        const prefixes = findPrefixes(centerNode);
        const suffixes = findSuffixes(centerNode);

        if (prefixes.length === 0 && suffixes.length === 0) {
                wordList.html("<div class='empty-msg'>No valid paths found.</div>");
                return;
        }

        const prefixList = prefixes.length > 0 ? prefixes : [""];
        const suffixList = suffixes.length > 0 ? suffixes : [""];

        const isSpecialNode = (centerNode.name === 'ROOT' || centerNode.name === 'END');
        const centerChar = isSpecialNode ? '' : centerNode.name;

        const wordsToRender = [];

        prefixList.forEach(pre => {
            suffixList.forEach(suf => {
                wordsToRender.push({ pre, center: centerChar, suf });
            });
        });

        if(wordsToRender.length === 0) {
                wordList.html("<div class='empty-msg'>No words found.</div>");
                return;
        }

        const listNode = wordList.node();
        let index = 0;
        
        function renderNextBatch() {
            const batchSize = 10; 
            const limit = Math.min(index + batchSize, wordsToRender.length);

            for (; index < limit; index++) {
                const item = wordsToRender[index];
                const div = document.createElement('div');
                div.className = 'generated-word';
                // Add staggered delay
                div.style.animationDelay = `${(index % 20) * 0.05}s`; 

                const centerSpan = item.center 
                    ? `<span class="char-focus">${item.center}</span>` 
                    : ''; 

                div.innerHTML = `<span class="char-ancestor">${item.pre}</span>${centerSpan}<span class="char-descendant">${item.suf}</span>`;
                listNode.appendChild(div);
            }

            if (index < wordsToRender.length) {
                requestAnimationFrame(renderNextBatch);
            }
        }
        
        renderNextBatch();
    }

    // DFS helpers
    function findPrefixes(targetNode) {
        let results = [];
        function backtrack(currentNode, currentString) {
            const incomingLinks = graphLinks.filter(l => l.target.id === currentNode.id);
            if (incomingLinks.length === 0) return;
            incomingLinks.forEach(link => {
                const parent = link.source;
                if (parent.name === 'ROOT') results.push(currentString);
                else backtrack(parent, parent.name + currentString);
            });
        }
        backtrack(targetNode, "");
        return results;
    }

    function findSuffixes(sourceNode) {
        let results = [];
        function forward(currentNode, currentString) {
            const outgoingLinks = graphLinks.filter(l => l.source.id === currentNode.id);
            outgoingLinks.forEach(link => {
                const child = link.target;
                if (child.name === 'END') results.push(currentString);
                else forward(child, currentString + child.name);
            });
        }
        forward(sourceNode, "");
        return results;
    }

    // --- Subgraph Helpers ---
    function getNodeChildren(node, links) {
        return links.filter(link => link.source.id === node.id).map(link => link.target);
    }

    function getNodeDescendants(node, links) {
        const descendants = new Set();
        const queue = [node];
        let head = 0;
        while (head < queue.length) {
            const currentNode = queue[head++];
            const children = getNodeChildren(currentNode, links);
            for (const child of children) {
                if (!descendants.has(child.id)) {
                    descendants.add(child.id);
                    queue.push(child);
                }
            }
        }
        return Array.from(descendants).map(id => graphNodes.find(n => n.id === id));
    }

    function getNodeAncestors(node, links) {
        const ancestors = new Set();
        const queue = [node];
        let head = 0;
        while (head < queue.length) {
            const currentNode = queue[head++];
            const parents = links.filter(link => link.target.id === currentNode.id).map(link => link.source);
            for (const parent of parents) {
                if (!ancestors.has(parent.id)) {
                    ancestors.add(parent.id);
                    queue.push(parent);
                }
            }
        }
        return Array.from(ancestors).map(id => graphNodes.find(n => n.id === id));
    }

    function calculateCompactLayout(centerNode, ancestors, descendants) {
        const layoutMap = new Map();
        layoutMap.set(centerNode.id, { x: centerNode.x, y: centerNode.y });

        const ancestorsByLevel = d3.group(ancestors, d => d.level);
        const ancLevels = Array.from(ancestorsByLevel.keys()).sort((a, b) => b - a);

        ancLevels.forEach(level => {
            const levelNodes = ancestorsByLevel.get(level);
            levelNodes.sort((a, b) => a.id - b.id);
            const levelDiff = centerNode.level - level;
            const y = centerNode.y - (levelDiff * SUBGRAPH_CONFIG.verticalSpacing);
            const width = (levelNodes.length - 1) * SUBGRAPH_CONFIG.horizontalSpacing;
            const startX = centerNode.x - (width / 2);
            levelNodes.forEach((node, i) => {
                layoutMap.set(node.id, { x: startX + (i * SUBGRAPH_CONFIG.horizontalSpacing), y: y });
            });
        });

        const descendantsByLevel = d3.group(descendants, d => d.level);
        const descLevels = Array.from(descendantsByLevel.keys()).sort((a, b) => a - b);

        descLevels.forEach(level => {
            const levelNodes = descendantsByLevel.get(level);
            levelNodes.sort((a, b) => a.id - b.id);
            const levelDiff = level - centerNode.level;
            const y = centerNode.y + (levelDiff * SUBGRAPH_CONFIG.verticalSpacing);
            const width = (levelNodes.length - 1) * SUBGRAPH_CONFIG.horizontalSpacing;
            const startX = centerNode.x - (width / 2);
            levelNodes.forEach((node, i) => {
                layoutMap.set(node.id, { x: startX + (i * SUBGRAPH_CONFIG.horizontalSpacing), y: y });
            });
        });

        return layoutMap;
    }

    // --- Interaction Logic ---
    function updatePanelInfo(d) {
        let content = `
            <p><strong>Name:</strong> "${d.name}"</p>
            <p><strong>ID:</strong> ${d.id}</p>
            <p><strong>Level:</strong> ${d.level}</p>
        `;
        nodeInfoDisplay.html(content);
    }

    function handleNodeClick(event, d) {
        event.stopPropagation();

        if (isGraphFrozen && frozenNodeId === d.id) {
            // Unfreeze
            isGraphFrozen = false;
            frozenNodeId = null;
            removeGraphHighlights();
            
            uiContainer.classed("visible", false);
            wordList.html(""); 
        } else {
            // Freeze (or switch node)
            isGraphFrozen = true;
            frozenNodeId = d.id;
            
            highlightGraphSegments(event, d);
            
            // Update Panel
            updatePanelInfo(d);
            uiContainer.classed("visible", true);
            wordList.html(""); // Clear old words
        }
    }

    function highlightGraphSegments(event, d) {
        simulation.stop();

        node.classed("dimmed", false)
            .classed("highlighted", false)
            .classed("ancestor", false)
            .classed("descendant", false);

        nodeLabel.classed("dimmed", false);

        link.classed("dimmed", false)
            .classed("highlighted-path", false)
            .classed("ancestor-link", false)
            .classed("descendant-link", false);

        const ancestors = getNodeAncestors(d, graphLinks);
        const descendants = getNodeDescendants(d, graphLinks);
        
        const ancestorIds = new Set(ancestors.map(n => n.id));
        const descendantIds = new Set(descendants.map(n => n.id));
        const allHighlightIds = new Set([d.id, ...ancestorIds, ...descendantIds]);

        const perfectPositions = calculateCompactLayout(d, ancestors, descendants);
        const interpolatedPositions = new Map();
        
        perfectPositions.forEach((target, id) => {
            const n = graphNodes.find(node => node.id === id);
            if (n) {
                const newX = n.originalFx + (target.x - n.originalFx) * SUBGRAPH_CONFIG.focusStrength;
                const newY = n.originalFy + (target.y - n.originalFy) * SUBGRAPH_CONFIG.focusStrength;
                interpolatedPositions.set(id, { x: newX, y: newY });
            }
        });

        // Classes
        node.classed("dimmed", n => !allHighlightIds.has(n.id));
        nodeLabel.classed("dimmed", n => !allHighlightIds.has(n.id));
        
        link.classed("dimmed", l => {
                const isAncestorLink = ancestorIds.has(l.source.id) && ancestorIds.has(l.target.id);
                const isDescendantLink = descendantIds.has(l.source.id) && descendantIds.has(l.target.id);
                const isConnectorUp = l.target.id === d.id && ancestorIds.has(l.source.id);
                const isConnectorDown = l.source.id === d.id && descendantIds.has(l.target.id);
                return !(isAncestorLink || isDescendantLink || isConnectorUp || isConnectorDown);
        });

        d3.select(event.currentTarget).classed("highlighted", true);
        node.filter(n => n.id === d.id).classed("highlighted", true);
        node.filter(n => ancestorIds.has(n.id)).classed("ancestor", true);
        node.filter(n => descendantIds.has(n.id)).classed("descendant", true);

        link.classed("ancestor-link", l => (ancestorIds.has(l.source.id) && ancestorIds.has(l.target.id)) || (l.target.id === d.id && ancestorIds.has(l.source.id)));
        link.classed("descendant-link", l => (descendantIds.has(l.source.id) && descendantIds.has(l.target.id)) || (l.source.id === d.id && descendantIds.has(l.target.id)));
        link.classed("highlighted-path", l => (l.source.id === d.id && descendantIds.has(l.target.id)) || (l.target.id === d.id && ancestorIds.has(l.source.id)));

        // Animation
        node.transition().duration(SUBGRAPH_CONFIG.transitionDuration)
            .attr("cx", n => interpolatedPositions.has(n.id) ? interpolatedPositions.get(n.id).x : n.x)
            .attr("cy", n => interpolatedPositions.has(n.id) ? interpolatedPositions.get(n.id).y : n.y);

        nodeLabel.transition().duration(SUBGRAPH_CONFIG.transitionDuration)
            .attr("x", n => interpolatedPositions.has(n.id) ? interpolatedPositions.get(n.id).x : n.x)
            .attr("y", n => interpolatedPositions.has(n.id) ? interpolatedPositions.get(n.id).y : n.y);

        link.transition().duration(SUBGRAPH_CONFIG.transitionDuration)
            .attr("x1", l => interpolatedPositions.has(l.source.id) ? interpolatedPositions.get(l.source.id).x : l.source.x)
            .attr("y1", l => interpolatedPositions.has(l.source.id) ? interpolatedPositions.get(l.source.id).y : l.source.y)
            .attr("x2", l => interpolatedPositions.has(l.target.id) ? interpolatedPositions.get(l.target.id).x : l.target.x)
            .attr("y2", l => interpolatedPositions.has(l.target.id) ? interpolatedPositions.get(l.target.id).y : l.target.y);
    }

    function removeGraphHighlights() {
        if (isGraphFrozen) return;

        node.attr("class", n => {
            let classes = `node`;
            if (n.name === 'ROOT') classes += ' root';
            if (n.name === 'END') classes += ' sink-end-node';
            return classes;
        });
        nodeLabel.attr("class", "node-label");
        link.attr("class", "link");

        const t = d3.transition().duration(SUBGRAPH_CONFIG.transitionDuration);

        node.transition(t)
            .attr("cx", d => d.originalFx)
            .attr("cy", d => d.originalFy);
        
        nodeLabel.transition(t)
            .attr("x", d => d.originalFx)
            .attr("y", d => d.originalFy);

        link.transition(t)
            .attr("x1", d => d.source.originalFx)
            .attr("y1", d => d.source.originalFy)
            .attr("x2", d => d.target.originalFx)
            .attr("y2", d => d.target.originalFy)
            .on("end", () => {
                graphNodes.forEach(n => {
                    n.x = n.originalFx;
                    n.y = n.originalFy;
                });
                simulation.alpha(0.1).restart();
            });
    }

    // Background Click -> Unfreeze
    svg.on("click", (event) => {
        const targetTag = event.target.tagName;
        if (targetTag !== "circle" && isGraphFrozen) {
            isGraphFrozen = false;
            frozenNodeId = null;
            removeGraphHighlights();
            
            uiContainer.classed("visible", false);
            wordList.html("");
        }
    });
});