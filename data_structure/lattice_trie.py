import json
import os

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        self.level = 0 # Level for lattice structure

    # These are crucial for canonicalizing nodes in a DAWG-like structure
    # A node's identity for merging is based on its character, its end-of-word status,
    # and the *canonical identity* of its children.
    # This requires a more sophisticated hashing/equality after children are canonicalized.
    # For now, a simple hash and equality based on direct children.
    # This will not achieve a full DAWG, but will allow some merging.

    # Node identity for merging is based on its character, its end-of-word status,
    # and the canonical identity of its children.
    # This requires a more sophisticated hashing/equality based on children's _get_canonical_key.
    
    def _get_canonical_key(self):
        # Create a tuple representing the node's structure for hashing.
        # This needs to be a stable representation, so sort children keys.
        
        # Canonicalization key considers the character, its is_end_of_word status,
        # and the canonical keys of its children.
        # This recursive definition ensures that entire suffixes are compared.
        
        children_for_key = []
        # Determine if this node represents the end of a word purely by having an '<END>' child link.
        # This creates a distinct, stable representation for canonicalization.
        strictly_ends_word_here = False

        for char, child in self.children.items():
            if char == "<END>" and child.char == "END": # Check if it's the actual end_node link
                strictly_ends_word_here = True
                # The canonical key of the END node is simple and stable, no recursion needed for it here.
                children_for_key.append(("<END>", ("END", True, ())))
            else:
                children_for_key.append((char, child._get_canonical_key()))
        
        children_repr = tuple(sorted(children_for_key))
        
        # The canonical key now includes:
        # 1. The character of the node.
        # 2. The sorted canonical representations of its children.
        # This provides a more precise and immutable key for merging.
        # The canonical identity is determined by the character, its direct end-of-word status,
        # and the canonical keys of its children.
        return (self.char, self.level, children_repr)


    # Note: We will NOT directly use __hash__ and __eq__ on Node objects for canonicalization
    # in the LatticeTrie's `minimized_nodes` map directly. Instead, we'll use `_get_canonical_key`
    # as the key for `minimized_nodes`. This avoids recursive hashing issues and allows explicit control.


class LatticeTrie:
    def __init__(self):
        self.root = Node()
        # Create a special sink node for all word endings
        self.end_node = Node(char="END")
        
        self.nodes = {self.root, self.end_node} # Keep track of all *unique* nodes created, including the end_node

        # Stores already canonicalized nodes (suffix-equivalent nodes)
        # Maps canonical_key (tuple from _get_canonical_key) -> canonical_node
        # Pre-add the end_node to minimized_nodes with its stable canonical key.
        self.minimized_nodes = {self.end_node._get_canonical_key(): self.end_node}
        
        self.words = [] # Re-add for _assign_levels
        
    def _get_canonical_node(self, node_to_canonicalize):
        # This function aims to find an existing canonical node that is equivalent
        # to node_to_canonicalize based on its structure (children, end-of-word).

        # It's assumed that when `_get_canonical_node` is called on a node, all its
        # children have already been processed and their canonical versions are in `minimized_nodes`.
        # This is ensured by the backward iteration in the `insert` method.

        canonical_key = node_to_canonicalize._get_canonical_key()

        if canonical_key in self.minimized_nodes:
            # If an equivalent canonical node already exists, return it.
            return self.minimized_nodes[canonical_key]
        else:
            # Otherwise, this node (or its structure) is new, so add it as a canonical node.
            self.minimized_nodes[canonical_key] = node_to_canonicalize
            return node_to_canonicalize

    def insert(self, word):
        word_lower = word.lower() # Convert word to lowercase
        path_nodes_stack = [] # Stack to store nodes for back-tracking and canonicalization
        current_node = self.root

        # Phase 1: Standard trie insertion (but keeping track of the path)
        for char in word_lower: # Use the lowercase version for insertion
            if char not in current_node.children:
                new_node = Node(char)
                current_node.children[char] = new_node
                self.nodes.add(new_node)
            current_node = current_node.children[char]
            path_nodes_stack.append(current_node)

        # Instead of marking the actual node as is_end_of_word, link it to the special end_node
        # And ensure the end_node receives the highest level from all incoming paths
        current_node.children["<END>"] = self.end_node # Use a special character for the link to END

        # Phase 2: Canonicalize nodes (simplified DAWG-like minimization)
        # Iterate backwards through the path to canonicalize nodes from leaves up.
        # This ensures that when a parent is canonicalized, its children are already canonical.
        for i in range(len(path_nodes_stack) - 1, -1, -1):
            node_to_canonicalize = path_nodes_stack[i]
            
            # Get the canonical version of this node based on its current structure
            canonical_version = self._get_canonical_node(node_to_canonicalize)

            # Check if canonicalization results in a different node (i.e., a merge occurred)
            if canonical_version is not node_to_canonicalize:
                # Merge properties from the redundant node to the canonical version
                canonical_version.level = max(canonical_version.level, node_to_canonicalize.level)

                # Replace the redundant node with the canonical version in its parent's children
                if i > 0:
                    parent_of_current = path_nodes_stack[i-1]
                    for char_key, child_val in parent_of_current.children.items():
                        if child_val is node_to_canonicalize:
                            parent_of_current.children[char_key] = canonical_version
                            break
                # Remove the redundant node from our set of active nodes
                self.nodes.discard(node_to_canonicalize)

    def _assign_levels(self):
        """
        Assigns levels to nodes in the Trie, where the level of a node is
        the length of the longest path from the root to that node.
        This is achieved using a single-pass topological sort-like BFS.
        """
        # Re-initialize levels for a robust level assignment.
        for node in self.nodes:
            node.level = -1 # Use -1 to indicate unvisited, or that level calculation is pending
        self.root.level = 0
        
        # Calculate in-degrees for all nodes to support a topological sort-like processing.
        # This ensures that a node is processed only after all its parent nodes have their final levels.
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for child_node in node.children.values():
                in_degree[child_node] += 1

        # Initialize a queue with nodes having an in-degree of 0 (typically just the root).
        queue = [node for node, degree in in_degree.items() if degree == 0]
        
        processed_count = 0

        while queue:
            current_node = queue.pop(0)
            processed_count += 1

            for child_node in current_node.children.items(): # Changed to .items() to get (char, child_node)
                # Update child node's level if a longer path is found through the current_node.
                if current_node.level != -1 and current_node.level + 1 > child_node[1].level: # Access child_node from tuple
                    child_node[1].level = current_node.level + 1
                
                # Decrement in-degree and add the child to the queue if all its parents have been processed.
                in_degree[child_node[1]] -= 1 # Access child_node from tuple
                if in_degree[child_node[1]] == 0:
                    queue.append(child_node[1]) # Access child_node from tuple
        
        print(f"DEBUG: Levels assigned using a single-pass topological sort-like BFS. Processed {processed_count} nodes.")

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

            nodes_data.append({
                "id": current_node_id,
                "name": current_node.char if current_node.char else "ROOT",
                "level": current_node.level # Re-add the level to node data
            })

            for char, child_node in current_node.children.items():
                # Special handling for the END node link
                if child_node is self.end_node and char == "<END>":
                    # Ensure the end_node itself is added to the graph nodes data if not already
                    if self.end_node not in node_id_map:
                        id_counter += 1
                        node_id_map[self.end_node] = id_counter
                        nodes_data.append({
                            "id": node_id_map[self.end_node],
                            "name": self.end_node.char,
                            "level": self.end_node.level # Re-add the level to the sink node
                        })
                    links_data.append({
                        "source": current_node_id,
                        "target": node_id_map[self.end_node],
                        "label": char
                    })
                else:
                    if child_node not in node_id_map: # If child not yet mapped, add to queue
                        queue_for_viz.append(child_node)
                        id_counter += 1
                        node_id_map[child_node] = id_counter
                    
                    child_node_id = node_id_map[child_node]

                    links_data.append({
                        "source": current_node_id,
                        "target": child_node_id,
                        "label": char
                    })

        # Apply max_nodes limit for visualization
        if len(nodes_data) > max_nodes:
            nodes_data = nodes_data[:max_nodes]
            # Filter links to only include visible nodes
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
