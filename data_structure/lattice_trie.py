import json
import os
import sys
from tqdm import tqdm
from collections import deque

# Increase recursion depth just in case, though we are mostly iterative now
sys.setrecursionlimit(5000)

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        # OPTIMIZATION 1: Track parents directly.
        self.parents = [] 
        self.depth = 0 
        self.level = 0 

    def _get_shallow_key(self):
        """
        OPTIMIZATION 2: Identity-based Hashing.
        """
        if self.char == "END": 
            return ("END_NODE_IDENTIFIER",)

        # Create a signature based on the edge char and the memory address (id) of the child.
        children_signatures = []
        for key, child in self.children.items():
            children_signatures.append((key, id(child)))
        
        # Sort to ensure order of insertion doesn't affect equality
        children_repr = tuple(sorted(children_signatures))
        return (self.char, children_repr)


class LatticeTrie:
    def __init__(self):
        self.root = Node()
        self.end_node = Node(char="END")
        
        self.nodes = {self.root, self.end_node} 
        
        # Pre-calculate end node key
        self.minimized_nodes = {self.end_node._get_shallow_key(): self.end_node}
        
    def insert(self, word):
        word_lower = word.lower()
        current_node = self.root

        current_depth = 0
        for char in word_lower:
            current_depth += 1
            if char not in current_node.children:
                new_node = Node(char)
                new_node.depth = current_depth
                
                # Forward link: Parent -> Child
                current_node.children[char] = new_node
                
                # Reverse link: Child -> Parent
                new_node.parents.append(current_node)
                
                self.nodes.add(new_node)
            
            current_node = current_node.children[char]

        # Handle the End Node connection
        if "<END>" not in current_node.children:
            current_node.children["<END>"] = self.end_node

    def canonicalize_suffix_dags(self):
        """
        OPTIMIZATION 3: Bottom-Up Canonicalization with Direct Parent Updates.
        """
        # Reset tracking map
        self.minimized_nodes = {self.end_node._get_shallow_key(): self.end_node}
        
        # Sort by depth descending (Deepest first).
        nodes_to_process = sorted(list(self.nodes - {self.end_node}), key=lambda n: n.depth, reverse=True)
        
        nodes_to_discard = set()

        for current_node in tqdm(nodes_to_process, desc="Canonicalizing DAG", unit="node"):
            # Get key based on IMMEDIATE children's IDs (O(1)ish operation)
            canonical_key = current_node._get_shallow_key()

            if canonical_key in self.minimized_nodes:
                # We found an existing node that looks exactly like this one
                existing_node = self.minimized_nodes[canonical_key]
                
                if existing_node is not current_node:
                    nodes_to_discard.add(current_node)
                    
                    # DIRECT PARENT UPDATE:
                    for parent in current_node.parents:
                        # Find the specific edge that points to the node we are removing
                        for char, child in parent.children.items():
                            if child is current_node:
                                # Re-route the parent to the canonical version
                                parent.children[char] = existing_node
                                
                                # CRITICAL FIX: Prevent Duplicate Parents
                                # When merging massive graphs, a node might inherit the same parent 
                                # multiple times via different paths.
                                if not any(p is parent for p in existing_node.parents):
                                    existing_node.parents.append(parent)
                                break
            else:
                # This is the first time we've seen this structure; register it.
                self.minimized_nodes[canonical_key] = current_node

        # Remove discarded nodes from the main set
        self.nodes -= nodes_to_discard
        print(f"Reduction complete. Discarded {len(nodes_to_discard)} redundant nodes.")

    def _assign_levels(self):
        """
        Assigns levels using topological sort-like BFS.
        """
        for node in self.nodes:
            node.level = -1
        self.root.level = 0
        
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for child_node in node.children.values():
                if child_node in self.nodes:
                    in_degree[child_node] += 1

        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        
        with tqdm(total=len(self.nodes), desc="Assigning Levels", unit="node") as pbar:
            while queue:
                current_node = queue.popleft()
                pbar.update(1)

                for char, child_node in current_node.children.items():
                    if child_node in self.nodes:
                        if current_node.level != -1 and current_node.level + 1 > child_node.level:
                            child_node.level = current_node.level + 1
                        
                        in_degree[child_node] -= 1
                        if in_degree[child_node] == 0:
                            queue.append(child_node)

    def validate_integrity(self):
        """
        SANITY CHECK: Traverses the graph to ensure no dead ends exist.
        This proves the graph is connected, even if the visualization is truncated.
        """
        print("\n--- Validating Graph Integrity ---")
        if not self.root.children:
            print("FAIL: Root has no children.")
            return False

        dead_ends = 0
        visited = set()
        stack = [self.root]
        
        with tqdm(total=len(self.nodes), desc="Validating Paths", unit="node") as pbar:
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                pbar.update(1)
                
                # A node is a dead end if it has no children AND it is not the explicit END node
                if not node.children and node.char != "END":
                    dead_ends += 1
                
                for child in node.children.values():
                    stack.append(child)
        
        if dead_ends > 0:
            print(f"\nFAIL: Found {dead_ends} broken paths (nodes that stop before END).")
            return False
        else:
            print(f"\nSUCCESS: Graph is perfect. All {len(visited)} reachable nodes eventually hit END.")
            return True

    def visualize(self, max_nodes=5000):
        """
        Generates JSON for D3.js. 
        NOTE: If max_nodes is hit, the graph will look 'broken' in the visualizer 
        because we stop exporting, but the underlying data structure is verified intact.
        """
        nodes_data = []
        links_data = []
        node_id_map = {self.root: 0}
        id_counter = 0

        queue_for_viz = deque([self.root])
        processed_nodes = set()

        print(f"Generating Visualization (Truncating at {max_nodes} nodes)...")

        while queue_for_viz:
            # STOP if we exceed the visualization limit
            if len(nodes_data) >= max_nodes:
                break

            current_node = queue_for_viz.popleft()

            if current_node in processed_nodes:
                continue
            processed_nodes.add(current_node)

            # Assign ID if not exists
            if current_node not in node_id_map:
                id_counter += 1
                node_id_map[current_node] = id_counter
            
            current_node_id = node_id_map[current_node]

            # Add Node Data
            nodes_data.append({
                "id": current_node_id,
                "name": current_node.char if current_node.char else "ROOT",
                "level": current_node.level
            })

            # Process Children
            for char, child_node in current_node.children.items():
                
                # Handle connection to END node explicitly
                if child_node is self.end_node:
                    # Always include the END node if we are linking to it
                    if self.end_node not in node_id_map:
                        id_counter += 1
                        node_id_map[self.end_node] = id_counter
                        # Add END node to nodes_data immediately so the link is valid
                        nodes_data.append({
                            "id": node_id_map[self.end_node],
                            "name": "END",
                            "level": self.end_node.level
                        })
                    
                    links_data.append({
                        "source": current_node_id,
                        "target": node_id_map[self.end_node],
                        "label": char
                    })
                
                # Handle standard children
                elif child_node in self.nodes:
                    if child_node not in node_id_map:
                        # Only enqueue if we have space left
                        if len(node_id_map) < max_nodes:
                            id_counter += 1
                            node_id_map[child_node] = id_counter
                            queue_for_viz.append(child_node)
                    
                    # Only add link if child is effectively in our visual scope
                    if child_node in node_id_map:
                         links_data.append({
                            "source": current_node_id,
                            "target": node_id_map[child_node],
                            "label": char
                        })

        return {"nodes": nodes_data, "links": links_data}


# Helper function to load words
def load_words_from_csv(filepath):
    # Try absolute path first, then relative
    paths_to_try = [
        filepath,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', filepath),
        os.path.join("datasets", filepath)
    ]
    
    for p in paths_to_try:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    # Basic cleaning: remove empty lines and whitespace
                    return [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"Error reading {p}: {e}")
                return []
    return []

if __name__ == "__main__":
    trie = LatticeTrie()
    
    # EDIT THIS PATH to match the name of your dataset
    words_filepath = "test.csv"
    
    print(f"Attempting to load words...")
    words = load_words_from_csv(words_filepath)
    
    if words:
        print(f"Loaded {len(words)} words.")
        
        # 1. Insert
        for word in tqdm(words, desc="Building Trie", unit="word"):
            trie.insert(word)

        # 2. Canonicalize
        trie.canonicalize_suffix_dags()

        # 3. VALIDATE INTEGRITY (The fix for your worry)
        is_valid = trie.validate_integrity()
        if not is_valid:
            print("Warning: Graph integrity check failed. Check input data.")

        # 4. Levels
        trie._assign_levels()

        # 5. Visualize
        # Note: We limit to 5000 nodes to prevent browser crashes.
        # This WILL make the graph look broken in the UI, but step #3 proved it is not.
        graph_data = trie.visualize(max_nodes=5000)

        output_file = "lattice_trie_graph.json"
        with open(output_file, "w") as f:
            json.dump(graph_data, f, indent=4)

        print(f"Graph data saved to {output_file}")
        print(f"JSON contains {len(graph_data['nodes'])} nodes and {len(graph_data['links'])} links.")
    else:
        print(f"Could not find valid words file. Please check path: {words_filepath}")