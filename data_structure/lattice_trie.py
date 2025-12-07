import json
import os

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        self.depth = 0 # Use depth for canonical key, set during insertion
        self.level = 0 # For visualization, assigned after insertion

    def _get_canonical_key(self):
        if self.char == "END": # Special handling for the end_node itself
            return ("END_NODE_IDENTIFIER",) # Unique, stable key for the end node

        children_for_key = []
        for char, child in self.children.items():
            if char == "<END>" and child.char == "END":
                # For the child being the actual end_node, its canonical key is its special identifier
                children_for_key.append(("<END>", ("END_NODE_IDENTIFIER",)))
            else:
                children_for_key.append((char, child._get_canonical_key()))
        
        children_repr = tuple(sorted(children_for_key))
        # Use depth for the canonical key to ensure stability during insertion
        return (self.char, self.depth, children_repr)


class LatticeTrie:
    def __init__(self):
        self.root = Node()
        self.end_node = Node(char="END")
        # No need to set depth for end_node, its _get_canonical_key handles it

        self.nodes = {self.root, self.end_node} 

        self.minimized_nodes = {self.end_node._get_canonical_key(): self.end_node}
        
    def _get_canonical_node(self, node_to_canonicalize):
        canonical_key = node_to_canonicalize._get_canonical_key()

        if canonical_key in self.minimized_nodes:
            return self.minimized_nodes[canonical_key]
        else:
            self.minimized_nodes[canonical_key] = node_to_canonicalize
            return node_to_canonicalize

    def insert(self, word):
        word_lower = word.lower()
        path_nodes_stack = []
        current_node = self.root

        # Phase 1: Standard trie insertion, setting node depth
        current_depth = 0
        for char in word_lower:
            current_depth += 1
            if char not in current_node.children:
                new_node = Node(char)
                new_node.depth = current_depth # Set depth during creation
                current_node.children[char] = new_node
                self.nodes.add(new_node)
            current_node = current_node.children[char]
            path_nodes_stack.append(current_node)

        current_node.children["<END>"] = self.end_node

        # Phase 2: Canonicalize nodes (simplified minimization)
        for i in range(len(path_nodes_stack) - 1, -1, -1):
            node_to_canonicalize = path_nodes_stack[i]
            
            canonical_version = self._get_canonical_node(node_to_canonicalize)

            if canonical_version is not node_to_canonicalize:
                # Replace the redundant node with the canonical version in its parent's children
                if i > 0:
                    parent_of_current = path_nodes_stack[i-1]
                    for char_key, child_val in parent_of_current.children.items():
                        if child_val is node_to_canonicalize:
                            parent_of_current.children[char_key] = canonical_version
                            break
                self.nodes.discard(node_to_canonicalize)

    def _assign_levels(self):
        """
        Assigns levels to nodes in the Trie, where the level of a node is
        the length of the longest path from the root to that node.
        This is achieved using a single-pass topological sort-like BFS.
        This is for visualization and does not affect canonicalization.
        """
        for node in self.nodes:
            node.level = -1
        self.root.level = 0
        
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for child_node in node.children.values():
                in_degree[child_node] += 1

        queue = [node for node, degree in in_degree.items() if degree == 0]
        
        while queue:
            current_node = queue.pop(0)

            for char, child_node in current_node.children.items():
                if current_node.level != -1 and current_node.level + 1 > child_node.level:
                    child_node.level = current_node.level + 1
                
                in_degree[child_node] -= 1
                if in_degree[child_node] == 0:
                    queue.append(child_node)

    def visualize(self, max_nodes=500):
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
                else:
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
    # Ensure correct path resolution when run from project root
    abs_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', filepath)
    with open(abs_filepath, 'r') as f:
        words = [line.strip() for line in f if line.strip()]
    return words

if __name__ == "__main__":
    trie = LatticeTrie()
    # Corrected path for script execution context
    words_filepath = "datasets\\lattice_trie_20_words.csv" 
    words = load_words_from_csv(words_filepath)

    for word in words:
        trie.insert(word)

    # Assign levels after all words are inserted and canonicalized
    trie._assign_levels()

    # Generate graph data for visualization
    graph_data = trie.visualize()

    # Save to a JSON file for the frontend
    # Ensure this is saved in the project root for the HTML to find it
    with open("lattice_trie_graph.json", "w") as f:
        json.dump(graph_data, f, indent=4)

    print(f"Lattice Trie built with {len(words)} words and graph data saved to lattice_trie_graph.json")
