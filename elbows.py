def organize_node_streams():
    """
    Inserts Dot nodes between each selected node and its inputs so that the connections 
    are strictly horizontal/vertical rather than diagonal. Incorporates logic similar to 
    Dots.py to handle multiple inputs and avoid duplicate Dots in the same location.
    
    Usage:
        1. Save this script to your Nuke script path (e.g., scripts/elbows.py).
        2. In Nuke, select the node(s) to organize.
        3. In the Script Editor:
            
            import elbows
            elbows.organize_node_streams()
    """
    import nuke

    def already_has_dot_at_position(connection_node, x, y):
        """
        Checks whether 'connection_node' has a Dot at the (x, y) position
        that is already wired up to it. Prevents creating duplicate dots.
        """
        if not connection_node:
            return False

        for idx in range(connection_node.inputs()):
            inp = connection_node.input(idx)
            if inp and inp.Class() == "Dot":
                if inp.xpos() == x and inp.ypos() == y:
                    return True
        return False

    def create_dot_between_nodes(input_node, current_node, input_index):
        """
        Create a Dot between 'input_node' and 'current_node' for the given input_index.
        The Dot is placed horizontally at input_node.xpos() and vertically at current_node.ypos().
        """
        # Get half the node's height to set the dot's font size
        node_half_height = current_node.screenHeight() * 0.5

        dot_x = input_node.xpos()
        dot_y = current_node.ypos()

        # Avoid duplicate Dots at the same position
        if already_has_dot_at_position(current_node, dot_x, dot_y):
            return  # Don't create another Dot

        dot = nuke.createNode("Dot", inpanel=False)
        dot.setXpos(dot_x)
        dot.setYpos(dot_y)
        dot["note_font_size"].setValue(node_half_height)

        # Rewire: input_node -> dot -> current_node
        dot.setInput(0, input_node)
        current_node.setInput(input_index, dot)

    def process_node(node, visited):
        """
        Recursively process each node's inputs. If an input is higher on the node graph 
        (input_node.yPos() < node.yPos()) and misaligned (input_node.xPos() != node.xPos()), 
        create a Dot node so the connection becomes a right angle.
        """
        if node in visited:
            return
        visited.add(node)

        # Check up to 3 inputs (Nuke generally allows up to 3 for merges, though some nodes have more)
        for i in range(node.inputs()):
            input_node = node.input(i)
            if not input_node:
                continue

            higher_input = (input_node.yPos() < node.yPos())
            x_misaligned = (input_node.xPos() != node.xPos())

            # If this input is above the current node and has a different X, insert a dot
            if higher_input and x_misaligned:
                create_dot_between_nodes(input_node, node, i)

            # Recurse upstream
            process_node(input_node, visited)

    selected_nodes = nuke.selectedNodes()
    visited_nodes = set()
    for sel_node in selected_nodes:
        process_node(sel_node, visited_nodes)
