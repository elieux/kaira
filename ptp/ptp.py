#!/usr/bin/env python
import sys
import base.project as project
from gen.codegen import Codegen

def main(args):

    p = project.load_project_from_file(args[0])
    gen = Codegen(p)

    if len(args) == 3 and args[1] == "--build":
        gen.build().write_to_file(args[2])
        return

    if len(args) == 3 and args[1] == "--place-user-fn":
        place = p.get_place(int(args[2]))
        print gen.get_place_user_fn_header(place),
        return

    if len(args) == 3 and args[1] == "--transition-user-fn":
        transition = p.get_transition(int(args[2]))
        print gen.get_transition_user_fn_header(transition),
        return

    print "Usage: ptp <project.xml> <action>"

if __name__ == '__main__':
    main(sys.argv[1:])
