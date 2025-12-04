import json
import os

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        self.is_end_of_word = False
        self.words_ending_here = [] # Actual words that end at this node
        self.count = 0 # How many words pass through this node (for DAWG-like context)

    # These are crucial for canonicalizing nodes in a DAWG-like structure
    # A node's identity for merging is based on its character, its end-of-word status,
    # and the *canonical identity* of its children.
    # This requires a more sophisticated hashing/equality after children are canonicalized.
    # For now, a simple hash and equality based on direct children.
    # This will not achieve a full DAWG, but will allow some merging.

    def _get_hash_key(self):
        # Create a tuple representing the node's structure for hashing.
        # This needs to be a stable representation, so sort children keys.
        children_repr = tuple(sorted((k, id(v)) for k, v in self.children.items()))
        return (self.char, self.is_end_of_word, children_repr, frozenset(self.words_ending_here))

    def __hash__(self):
        return hash(self._get_hash_key())

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self._get_hash_key() == other._get_hash_key()


class LatticeTrie:
    def __init__(self):
        self.root = Node()
        # Stores already canonicalized nodes (suffix-equivalent nodes)
        # Maps (char, frozenset_of_children_and_end_flag) -> canonical_node
        self.minimized_nodes = {} # Keyed by a stable representation of node structure
        self.nodes = {self.root} # Keep track of all *unique* nodes created

    def _get_canonical_node(self, node_to_canonicalize):
        # This function aims to find an existing canonical node that is equivalent
        # to node_to_canonicalize based on its structure (children, end-of-word, words ending here).
        # This is typically applied bottom-up in DAWG construction.

        # Before canonicalizing the current node, ensure its children are canonical.
        # This requires recursion or a stack-based approach if done during insertion.
        # For this simplified approach, node_to_canonicalize's children should already be
        # "canonical enough" for this level of merging.

        # The key must reflect the children's *canonical* identity, not just their instance ID.
        # This requires _get_hash_key to be recursive on canonical children.
        # Let's simplify this for now to avoid infinite recursion / premature canonicalization.
        
        # A simple, potentially imperfect approach for merging:
        # Create a representation of the node based on its char, end status, and the IDs of its children.
        # This works if child IDs are stable (which they are once a node is canonical).
        
        # Build a key based on the node's properties.
        # Using IDs of children implies that the children themselves are canonical.
        # This is where DAWG construction gets tricky with incremental insertion.
        children_canonical_ids = frozenset((k, id(v)) for k, v in node_to_canonicalize.children.items())
        key = (node_to_canonicalize.char, node_to_canonicalize.is_end_of_word, children_canonical_ids, frozenset(node_to_canonicalize.words_ending_here))


        if key in self.minimized_nodes:
            return self.minimized_nodes[key]
        else:
            self.minimized_nodes[key] = node_to_canonicalize
            return node_to_canonicalize

    def insert(self, word):
        path_nodes_stack = [] # Stack to store nodes for back-tracking and canonicalization
        current_node = self.root

        # Phase 1: Standard trie insertion (but keeping track of the path)
        for char in word:
            if char not in current_node.children:
                new_node = Node(char)
                current_node.children[char] = new_node
                self.nodes.add(new_node)
            current_node = current_node.children[char]
            current_node.count += 1 # Increment count of words passing through
            path_nodes_stack.append(current_node)

        current_node.is_end_of_word = True
        current_node.words_ending_here.append(word)

        # Phase 2: Canonicalize nodes (simplified DAWG-like minimization)
        # Iterate backwards through the path to canonicalize nodes from leaves up.
        # This ensures that when a parent is canonicalized, its children are already canonical.
        for i in range(len(path_nodes_stack) - 1, -1, -1):
            node_to_canonicalize = path_nodes_stack[i]
            
            # Get the canonical version of this node based on its current structure
            canonical_version = self._get_canonical_node(node_to_canonicalize)

            if canonical_version is not node_to_canonicalize:
                # This means 'node_to_canonicalize' is a duplicate of an existing 'canonical_version'.
                # We need to replace 'node_to_canonicalize' with 'canonical_version' in its parent's children.
                if i > 0:
                    parent_of_current = path_nodes_stack[i-1]
                    for char_key, child_val in parent_of_current.children.items():
                        if child_val is node_to_canonicalize:
                            parent_of_current.children[char_key] = canonical_version
                            break
                else: # If it's the first node in the path (a child of root)
                    # This case implies the root's child needs to be swapped.
                    # This is implicitly handled by _get_canonical_node if root's children are registered.
                    # For simplicity, we assume root's immediate children are handled via the canonicalization logic
                    # and won't be replaced directly here.
                    pass
                self.nodes.discard(node_to_canonicalize) # Remove the redundant node

    def visualize(self, max_nodes=500):
        nodes_data = []
        links_data = []
        node_id_map = {self.root: 0} # Map node objects to unique IDs
        id_counter = 0

        # Ensure all unique nodes (after insertion and merging) are assigned an ID
        # and their data is prepared.
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

            node_suffixes = []
            if current_node.is_end_of_word:
                node_suffixes.extend(current_node.words_ending_here)

            nodes_data.append({
                "id": current_node_id,
                "name": current_node.char if current_node.char else "ROOT",
                "isEndOfWord": current_node.is_end_of_word,
                "wordCount": current_node.count,
                "wordsEndingHere": list(current_node.words_ending_here),
                "suffixes": node_suffixes
            })

            for char, child_node in current_node.children.items():
                if child_node not in node_id_map: # If child not yet mapped, add to queue
                    queue_for_viz.append(child_node)
                    id_counter += 1
                    node_id_map[child_node] = id_counter
                
                child_node_id = node_id_map[child_node]

                links_data.append({
                    "source": current_node_id,
                    "target": child_node_id,
                    "label": char,
                    "type": "prefix"
                })

        # Apply max_nodes limit for visualization
        if len(nodes_data) > max_nodes:
            # Sort by wordCount to prioritize more common paths, or other heuristics
            nodes_data.sort(key=lambda x: x['wordCount'], reverse=True)
            nodes_data = nodes_data[:max_nodes]
            # Filter links to only include visible nodes
            valid_node_ids = {node['id'] for node in nodes_data}
            links_data = [link for link in links_data if link['source'] in valid_node_ids and link['target'] in valid_node_ids]
            print(f"Warning: Graph has {len(nodes_data)} unique nodes, displaying {len(nodes_data)} after truncation to {max_nodes}.")


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
    words_filepath = "datasets/20-common-english-words.csv" 
    words = load_words_from_csv(words_filepath)

    for word in words:
        trie.insert(word)

    # Generate graph data for visualization
    graph_data = trie.visualize()

    # Save to a JSON file for the frontend
    # Ensure this is saved in the project root for the HTML to find it
    with open("lattice_trie_graph.json", "w") as f:
        json.dump(graph_data, f, indent=4)

    print(f"Lattice Trie built with {len(words)} words and graph data saved to lattice_trie_graph.json")
