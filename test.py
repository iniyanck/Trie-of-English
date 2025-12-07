import json

def generate_words_from_json(json_file_path):
    """
    Reads a JSON file, extracts and generates all words from it.
    Assumes the JSON structure contains nodes with 'char' and 'is_end_of_word' properties.
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        words = []
        node_map = {node['id']: node for node in data['nodes']}
        
        # Build adjacency list for easier traversal
        adj_list = {node_id: [] for node_id in node_map}
        for link in data['links']:
            adj_list[link['source']].append({'target': link['target'], 'label': link['label']})

        end_node_id = 16 # ID of the "END" node

        def traverse(node_id, current_word):
            # Check if this node leads to an end of word
            for neighbor in adj_list.get(node_id, []):
                if neighbor['target'] == end_node_id:
                    words.append(current_word)
            
            # Continue traversal to other children
            for neighbor in adj_list.get(node_id, []):
                if neighbor['target'] != end_node_id:
                    child_node = node_map[neighbor['target']]
                    # Use neighbor['label'] as the character to append, as it represents the edge
                    traverse(neighbor['target'], current_word + neighbor['label'])

        # Start traversal from the root node (assuming node 0 is the root)
        if data and 'nodes' in data and len(data['nodes']) > 0:
            # We start from the children of the root node (id 0)
            for link in adj_list.get(0, []):
                if link['target'] != end_node_id: # Ensure not to directly link to END from root
                    child_node = node_map[link['target']]
                    traverse(link['target'], link['label'])
                
        return words

    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {json_file_path}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

if __name__ == "__main__":
    json_file = "lattice_trie_graph.json" # Assuming the JSON file is in the same directory
    generated_words = generate_words_from_json(json_file)
    if generated_words:
        print("Generated words:")
        for word in generated_words:
            print(word)
        print(f"\nTotal words generated: {len(generated_words)}")
