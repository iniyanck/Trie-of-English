import json
import os
from tqdm import tqdm

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        # OPTIMIZATION 1: Track parents directly. 
        # This allows O(1) access to parents instead of searching the whole graph.
        self.parents = [] 
        self.depth = 0 
        self.level = 0 

    def _get_shallow_key(self):
        """
        OPTIMIZATION 2: Identity-based Hashing.
        Instead of recursively generating a key based on the entire subgraph structure,
        we rely on the fact that we process Deepest-Nodes-First. 
        
        Therefore, if two nodes have children with the exact same Memory IDs (id()),
        those children are effectively the same nodes.
        """
        if self.char == "END": 
            return ("END_NODE_IDENTIFIER",)

        # Create a signature based on the edge char and the memory address (id) of the child.
        # This is extremely fast compared to recursive string/tuple generation.
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
                
                # OPTIMIZATION 1: Reverse link: Child -> Parent
                new_node.parents.append(current_node)
                
                self.nodes.add(new_node)
            
            current_node = current_node.children[char]

        # Handle the End Node connection
        if "<END>" not in current_node.children:
            current_node.children["<END>"] = self.end_node
            # We treat the end node as a singleton, so we don't strictly need to track 
            # its parents for reduction, but it keeps logic consistent if you ever expand logic.
            # self.end_node.parents.append(current_node) 

    def canonicalize_suffix_dags(self):
        """
        OPTIMIZATION 3: Bottom-Up Canonicalization with Direct Parent Updates.
        """
        # Reset tracking map
        self.minimized_nodes = {self.end_node._get_shallow_key(): self.end_node}
        
        # Sort by depth descending (Deepest first).
        # This ensures that when we process a node, its children have already been processed/merged.
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
                    # Iterate through the parents of the node we are deleting (current_node)
                    # and tell them to point to the kept node (existing_node) instead.
                    for parent in current_node.parents:
                        # Find the specific edge that points to the node we are removing
                        for char, child in parent.children.items():
                            if child is current_node:
                                # Re-route the parent to the canonical version
                                parent.children[char] = existing_node
                                
                                # CRITICAL: Register the parent with the new child!
                                # Because 'existing_node' is now being pointed to by 'parent',
                                # 'existing_node' must know about this new parent for future merges up the chain.
                                existing_node.parents.append(parent)
                                break
            else:
                # This is the first time we've seen this structure; register it.
                self.minimized_nodes[canonical_key] = current_node

        # Remove discarded nodes from the main set
        self.nodes -= nodes_to_discard

        # Optional: Clear parent lists to free memory if visualization doesn't need reverse lookups
        # for node in self.nodes:
        #     node.parents = []

    def _assign_levels(self):
        """
        Assigns levels to nodes in the Trie using topological sort-like BFS.
        """
        for node in self.nodes:
            node.level = -1
        self.root.level = 0
        
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for child_node in node.children.values():
                if child_node in self.nodes:
                    in_degree[child_node] += 1

        queue = [node for node, degree in in_degree.items() if degree == 0]
        
        with tqdm(total=len(self.nodes), desc="Assigning Levels", unit="node") as pbar:
            while queue:
                current_node = queue.pop(0)
                pbar.update(1)

                for char, child_node in current_node.children.items():
                    if child_node in self.nodes:
                        if current_node.level != -1 and current_node.level + 1 > child_node.level:
                            child_node.level = current_node.level + 1
                        
                        in_degree[child_node] -= 1
                        if in_degree[child_node] == 0:
                            queue.append(child_node)

    def visualize(self, max_nodes=5000):
        nodes_data = []
        links_data = []
        node_id_map = {self.root: 0}
        id_counter = 0

        processed_nodes = set()
        queue_for_viz = [self.root]

        while queue_for_viz:
            current_node = queue_for_viz.pop(0)

            if current_node in processed_nodes:
                continue
            processed_nodes.add(current_node)

            if current_node not in node_id_map:
                id_counter += 1
                node_id_map[current_node] = id_counter
            current_node_id = node_id_map[current_node]

            nodes_data.append({
                "id": current_node_id,
                "name": current_node.char if current_node.char else "ROOT",
                "level": current_node.level
            })

            for char, child_node in current_node.children.items():
                if child_node is self.end_node and char == "<END>":
                    if self.end_node not in node_id_map:
                        id_counter += 1
                        node_id_map[self.end_node] = id_counter
                        nodes_data.append({
                            "id": node_id_map[self.end_node],
                            "name": self.end_node.char,
                            "level": self.end_node.level
                        })
                    links_data.append({
                        "source": current_node_id,
                        "target": node_id_map[self.end_node],
                        "label": char
                    })
                elif child_node in self.nodes:
                    if child_node not in node_id_map:
                        queue_for_viz.append(child_node)
                        id_counter += 1
                        node_id_map[child_node] = id_counter
                    
                    child_node_id = node_id_map[child_node]

                    links_data.append({
                        "source": current_node_id,
                        "target": child_node_id,
                        "label": char
                    })

        if len(nodes_data) > max_nodes:
            nodes_data = nodes_data[:max_nodes]
            valid_node_ids = {node['id'] for node in nodes_data}
            links_data = [link for link in links_data if link['source'] in valid_node_ids and link['target'] in valid_node_ids]
            print(f"Warning: Graph has {len(processed_nodes)} unique nodes, displaying {len(nodes_data)} after truncation to {max_nodes}.")

        return {"nodes": nodes_data, "links": links_data}


# Helper function to load words from a CSV
def load_words_from_csv(filepath):
    abs_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', filepath)
    # Basic error handling for path
    if not os.path.exists(abs_filepath):
        # Try local directory if '..' failed
        abs_filepath = filepath
        
    try:
        with open(abs_filepath, 'r') as f:
            words = [line.strip() for line in f if line.strip()]
        return words
    except FileNotFoundError:
        return []

if __name__ == "__main__":
    trie = LatticeTrie()
    
    # Adjust path if necessary
    words_filepath = os.path.join("datasets", "max_words.csv")
    
    print(f"Attempting to load from: {words_filepath}")
    words = load_words_from_csv(words_filepath)
    
    if words:
        print(f"Loaded {len(words)} words.")
        
        # Phase 1: Insertion
        for word in tqdm(words, desc="Building Trie", unit="word"):
            trie.insert(word)

        # Phase 2: Canonicalize (Optimized)
        trie.canonicalize_suffix_dags()

        # Phase 3: Assign levels
        trie._assign_levels()

        # Generate graph data
        print("Generating visualization data...")
        graph_data = trie.visualize()

        # Save to JSON
        output_file = "lattice_trie_graph.json"
        with open(output_file, "w") as f:
            json.dump(graph_data, f, indent=4)

        print(f"Lattice Trie built with {len(words)} words.")
        print(f"Graph data saved to {output_file}")
    else:
        print(f"No words found or file error at {words_filepath}.")