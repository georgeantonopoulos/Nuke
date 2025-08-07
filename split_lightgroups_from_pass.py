#!/usr/bin/env python
"""
Nuke Python Script: Split Lightgroup Passes

This script takes a selected Shuffle node and automatically creates separate
shuffle nodes for all lightgroup variants of the pass, then combines them
using Merge (plus) nodes.

Author: Nuke Python Script
"""

import nuke

def split_lightgroups_from_pass():
    """
    Main function to split lightgroup passes from a selected Shuffle node.
    
    This function:
    1. Gets the selected Shuffle node and its 'in' knob value (e.g., 'specular')
    2. Searches for all related lightgroup layers (e.g., 'specular_Dome', 'specular_Lab_btm')
    3. Creates new Shuffle nodes for each lightgroup variant
    4. Creates Merge (plus) nodes to combine all variants
    5. Disconnects the original Shuffle node
    """
    
    # Check if a node is selected
    try:
        selected_node = nuke.selectedNode()
    except ValueError:
        nuke.message("Please select a Shuffle node first.")
        return
    
    # Verify it's a Shuffle node
    if selected_node.Class() != "Shuffle2":
        nuke.message("Selected node must be a Shuffle2 node.")
        return
    
    # Get the 'in1' knob value (the pass name like 'specular', 'reflection', etc.)
    pass_name = selected_node['in1'].value()
    if not pass_name:
        nuke.message("The selected Shuffle2 node's 'in1' knob is empty.")
        return
    
    # Get the input node (source of the multi-layer EXR)
    input_node = selected_node.input(0)
    if not input_node:
        nuke.message("The selected Shuffle node has no input.")
        return
    
    # Get all available layers from the input node
    all_layers = input_node.channels()
    
    # Extract layer names (everything before the dot)
    layer_names = list(set([channel.split('.')[0] for channel in all_layers]))
    
    # Find all lightgroup variants for the selected pass
    lightgroup_layers = []
    for layer in layer_names:
        if layer.startswith(pass_name + "_"):
            lightgroup_layers.append(layer)
    
    if not lightgroup_layers:
        nuke.message(f"No lightgroup variants found for pass '{pass_name}'.")
        return
    
    # Sort the layers for consistent ordering
    lightgroup_layers.sort()
    
    # Get the position of the original shuffle node for layout
    original_x = selected_node['xpos'].value()
    original_y = selected_node['ypos'].value()
    
    # Store the output connection of the original shuffle (if any)
    original_dependents = selected_node.dependent()
    
    # Create shuffle nodes for each lightgroup variant
    shuffle_nodes = []
    x_offset = 0
    y_offset = 150  # Vertical offset for new nodes
    
    for i, layer in enumerate(lightgroup_layers):
        # Create new shuffle2 node
        new_shuffle = nuke.nodes.Shuffle2(
            inputs=[input_node],
            label=layer
        )
        
        # Set the layer for this shuffle2
        new_shuffle['in1'].setValue(layer)
        
        # Position the node
        new_shuffle['xpos'].setValue(original_x + x_offset)
        new_shuffle['ypos'].setValue(original_y + y_offset)
        
        # Store the shuffle node
        shuffle_nodes.append(new_shuffle)
        
        # Update position for next node
        x_offset += 120  # Horizontal spacing between nodes
    
    # Create merge chain: first shuffle goes directly to parent, subsequent shuffles get merged
    if len(shuffle_nodes) > 0:
        # First shuffle connects directly to the parent source node
        current_output = shuffle_nodes[0]
        
        # Create merge nodes for remaining shuffles (starting from second shuffle)
        merge_y_offset = y_offset + 120  # Position merges below shuffles
        
        for i in range(1, len(shuffle_nodes)):
            # Create merge node: B=previous result (input 0), A=current shuffle (input 1)
            merge_node = nuke.nodes.Merge2(operation='plus')
            merge_node.setInput(0, current_output)        # B input (input 0): previous result
            merge_node.setInput(1, shuffle_nodes[i])      # A input (input 1): current lightgroup shuffle
            
            # Position merge below current shuffle
            merge_node['xpos'].setValue(shuffle_nodes[i]['xpos'].value())
            merge_node['ypos'].setValue(original_y + merge_y_offset)
            
            # This merge becomes the input for the next iteration
            current_output = merge_node
        
        final_output = current_output
    else:
        # Fallback if no lightgroups found
        final_output = selected_node
    
    # Reconnect any nodes that were connected to the original shuffle
    for dependent in original_dependents:
        for i in range(dependent.inputs()):
            if dependent.input(i) == selected_node:
                dependent.setInput(i, final_output)
    
    # Disconnect the original shuffle node from its input
    selected_node.setInput(0, None)
    
    # Position the original shuffle node to the side
    selected_node['xpos'].setValue(original_x - 200)
    selected_node['ypos'].setValue(original_y)
    
    print(f"Successfully split '{pass_name}' into {len(lightgroup_layers)} lightgroup variants:")
    for layer in lightgroup_layers:
        print(f"  - {layer}")

# Run the function when script is executed
if __name__ == "__main__":
    split_lightgroups_from_pass()
