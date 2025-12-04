import json
import os

class Node:
    def __init__(self, char=''):
        self.char = char
        self.children = {}
        self.is_end_of_word = False
        self.words_ending_here = [] # Actual words that end at this node
        self.count = 0 # How many words pass through this node (for DAWG-like context)
        self.level = 0 # Level for lattice structure

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
        # Removed frozenset(self.words_ending_here) from hash key to allow suffix convergence
        return (self.char, self.is_end_of_word, children_repr)

    def __hash__(self):
        return hash(self._get_hash_key())

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        # Compare based on _get_hash_key, which now excludes words_ending_here
        return self._get_hash_key() == other._get_hash_key()


class LatticeTrie:
    def __init__(self):
        self.root = Node()
        # Create a special sink node for all word endings
        self.end_node = Node(char="END")
        self.end_node.is_end_of_word = True # Mark it as a special end node
        self.nodes = {self.root, self.end_node} # Keep track of all *unique* nodes created, including the end_node

        # Stores already canonicalized nodes (suffix-equivalent nodes)
        # Maps (char, frozenset_of_children_and_end_flag) -> canonical_node
        self.minimized_nodes = {} # Keyed by a stable representation of node structure
        
        self.words = [] # To store all words for max_word_length in _assign_levels

    def _get_canonical_node(self, node_to_canonicalize):
        # This function aims to find an existing canonical node that is equivalent
        # to node_to_canonicalize based on its structure (children, end-of-word).

        # Build a key based on the node's properties.
        # Using IDs of children implies that the children themselves are canonical.
        children_canonical_ids = frozenset((k, id(v)) for k, v in node_to_canonicalize.children.items())
        # Removed frozenset(node_to_canonicalize.words_ending_here) from key
        key = (node_to_canonicalize.char, node_to_canonicalize.is_end_of_word, children_canonical_ids)

        if key in self.minimized_nodes:
            return self.minimized_nodes[key]
        else:
            self.minimized_nodes[key] = node_to_canonicalize
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
            current_node.count += 1 # Increment count of words passing through
            path_nodes_stack.append(current_node)

        # Instead of marking the actual node as is_end_of_word, link it to the special end_node
        # And ensure the end_node receives the highest level from all incoming paths
        current_node.children["<END>"] = self.end_node # Use a special character for the link to END
        self.words.append(word_lower) # Store the original word for level assignment, but lowercase
        # The words_ending_here will still be stored on the original node for context if needed,
        # but the actual "end" will be signified by linking to the end_node.
        current_node.is_end_of_word = True # Keep this to retain word information for visualization
        current_node.words_ending_here.append(word_lower) # Store the lowercase version

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
                if node_to_canonicalize.is_end_of_word:
                    canonical_version.is_end_of_word = True
                canonical_version.words_ending_here.extend(node_to_canonicalize.words_ending_here)
                canonical_version.count += node_to_canonicalize.count # Aggregate counts for merged paths

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
        Assigns levels to nodes in the Trie using a breadth-first traversal.
        The level of a node is max(parent_level) + 1.
        """
        queue = [(self.root, 0)]
        # Use a dictionary to keep track of the maximum level reached for each node,
        # as a node might be reached from multiple paths (due to DAWG-like merging).
        # Initialize all node levels to 0 and then update.
        for node in self.nodes:
            node.level = 0
        self.root.level = 0 # Root is level 0

        processed_for_level = set()

        while queue:
            current_node, current_level = queue.pop(0)

            # Only update level if current_level is greater than the already assigned level
            # This handles cases where a node is reached by multiple paths
            if current_level > current_node.level:
                current_node.level = current_level
            
            # Add to processed set once its level is finalized for this iteration
            # (though it might be updated again if a higher path is found later)
            processed_for_level.add(current_node)

            for child_node in current_node.children.values():
                # Enqueue if the child's potential new level is higher than its current level
                # Or if it hasn't been processed yet.
                if current_node.level + 1 > child_node.level or child_node not in processed_for_level:
                    queue.append((child_node, current_node.level + 1))
        
        # A second pass or a more robust BFS might be needed to ensure "greatest of two prefixes".
        # The above BFS might not guarantee the max if a shorter path is processed first.
        # Let's refine this with a proper Bellman-Ford-like approach or iterative BFS for max levels.

        # Re-initialize levels for a robust level assignment
        for node in self.nodes:
            node.level = -1 # Use -1 to indicate unvisited, or that level calculation is pending
        self.root.level = 0
        
        # This will store nodes to process, ensuring we process all paths.
        # queue elements will be (node, potential_level)
        queue = [(self.root, 0)]
        
        # Keep track of nodes whose levels might still need updates, and a visited set for BFS structure.
        nodes_in_queue = {self.root} # Keep track of nodes currently in queue to avoid duplicates
        
        # Standard BFS for initial levels
        print(f"DEBUG: Starting initial BFS for level assignment. Total nodes: {len(self.nodes)}")
        while queue:
            current_node, current_level = queue.pop(0)
            nodes_in_queue.discard(current_node) # Remove from in-queue set

            # If we found a higher level for this node, update it
            if current_level > current_node.level:
                current_node.level = current_level
            
            for child_node in current_node.children.values():
                # If a path through current_node results in a higher level for child_node
                if current_node.level + 1 > child_node.level:
                    child_node.level = current_node.level + 1
                    # Add to queue only if it's not already in the queue to avoid redundant processing
                    if child_node not in nodes_in_queue:
                        queue.append((child_node, child_node.level))
                        nodes_in_queue.add(child_node)

        # After the initial BFS, perform a few more passes to propagate max levels
        # This is essentially relaxing edges repeatedly, similar to Bellman-Ford for longest path
        # since cycles are not present (it's a DAG). Max iterations = max path length.
        # In a trie, max path length is max word length.
        max_word_length = max(len(word) for word in self.words) if hasattr(self, 'words') and self.words else 50 # Heuristic max word length
        print(f"DEBUG: Max word length: {max_word_length}. Starting {max_word_length + 1} additional passes.")

        for i in range(max_word_length + 1): # Max path length + 1 iterations
            updated_in_pass = False
            for node in list(self.nodes): # Iterate over a copy as self.nodes might change
                for char_key, child_node in node.children.items():
                    # If this is the special link to the end_node, handle it
                    if child_node is self.end_node:
                        # The end_node's level should be the max of all its incoming parents + 1
                        if node.level != -1 and node.level + 1 > self.end_node.level:
                            self.end_node.level = node.level + 1
                            updated_in_pass = True
                    elif node.level != -1 and node.level + 1 > child_node.level:
                        child_node.level = node.level + 1
                        updated_in_pass = True
            # print(f"DEBUG: Pass {i+1}/{max_word_length + 1} completed. Updated: {updated_in_pass}")
            if not updated_in_pass:
                print(f"DEBUG: Levels stable after {i+1} passes.")
                break # No levels were updated, so we've reached a stable state

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
            # Only include actual words for non-END nodes
            if current_node.is_end_of_word and current_node is not self.end_node:
                node_suffixes.extend(current_node.words_ending_here)

            nodes_data.append({
                "id": current_node_id,
                "name": current_node.char if current_node.char else "ROOT",
                "isEndOfWord": current_node.is_end_of_word and current_node is not self.end_node, # Only mark as true if not the sink
                "wordCount": current_node.count,
                "wordsEndingHere": list(current_node.words_ending_here) if current_node is not self.end_node else [],
                "suffixes": node_suffixes,
                "level": current_node.level # Add the level to node data
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
                            "isEndOfWord": True, # The sink node is always an end of word
                            "wordCount": sum(len(w.words_ending_here) for w in self.nodes if w.is_end_of_word and w is not self.end_node), # Aggregate count
                            "wordsEndingHere": [], # Actual words are associated with the preceding nodes
                            "suffixes": [],
                            "level": self.end_node.level
                        })
                    links_data.append({
                        "source": current_node_id,
                        "target": node_id_map[self.end_node],
                        "label": char,
                        "type": "ends_word" # Special link type for visualization
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

    def search(self, word):
        word_lower = word.lower()  # Convert search word to lowercase
        current_node = self.root
        for char in word_lower:
            if char not in current_node.children:
                return False
            current_node = current_node.children[char]
        # A word is found if the path leads to a node and that node is marked as an end of a word
        # or if it has a link to the special end_node.
        return current_node.is_end_of_word or ("<END>" in current_node.children and current_node.children["<END>"] is self.end_node)


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
