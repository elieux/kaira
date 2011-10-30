
import emitter
import writer
import base.utils as utils
from base.neltypes import Type, t_int, t_string

from builder import t_place, get_ordered_types, get_edges_mathing

def ca_token(t):
    return Type("__Token", [t])

class Codegen(object):

    def __init__(self, project):
        self.emitter = emitter.Emitter()
        self.writer = writer.Writer()
        self.project = project

    def line(self, string, *args, **kw):
        self.writer.line(string, *args, **kw)

    def emptyline(self):
        self.writer.emptyline()

    def indent_push(self):
        self.writer.indent_push()

    def indent_pop(self):
        self.writer.indent_pop()

    def write_header(self):
        self.line("/* This file is automatically generated")
        self.line("   do not edit this file directly! */")
        self.emptyline()
        self.line('#include <cailie.h>')
        self.line('#include <algorithm>')
        self.emptyline()

    def write_main(self):
        self.line("int main(int argc, char **argv)")
        self.block_begin()
        self.line("ca_project_description({0});", self.emitter.const_string(self.project.description))
        self.line("ca_init(argc, argv, 0, NULL, NULL, NULL);")
        for net in self.project.nets:
            self.register_net(net)
        defs = [ "def_" + str(net.id) for net in self.project.nets ]
        self.line("CaNetDef *defs[] = {{{0}}};", ",".join(defs))
        self.line("ca_main({0}, defs);", len(defs));
        self.line("return 0;")
        self.block_end()

    def register_net(self, net):
        self.line("CaNetDef *def_{0.id} = new CaNetDef({0.id}, {1}, spawn_{0.id});", net,
                     len(net.transitions))
        for i, tr in enumerate(net.transitions):
            self.line("def_{0.id}->register_transition({2}, {1.id},(CaEnableFn*) enable_{1.id});",
                        net, tr, i)

    def get_writer(self):
        return self.writer

    def write_class(self, cls):
        cls.write(self.w)

    def add_tuple_class(self, t):
        class_name = t.get_safe_name()
        self.write_class_head(class_name)
        decls = [ ("t{0}".format(i), ta) for i, ta in enumerate(t.args) ]
        for name, ta in decls:
            self.write_var_decl(name, ta)

        self.write_constructor(class_name, decls, [ "{0}({0})".format(name) for name, _ in decls ])
        self.write_method_end()

        self.write_constructor(class_name, [], [])
        self.write_method_end()

        self.write_method_start("std::string as_string()")
        self.line('return "Tuple";')
        self.write_method_end()
        self.write_class_end()

    def write_types(self):
        for t in get_ordered_types(self.project):
            if t.name == "":
                self.add_tuple_class(t)

    def write_var_struct(self, tr):
        self.write_class_head("Vars_{0.id}".format(tr))
        context = tr.get_context()
        for key in context:
            self.write_var_decl(key, context[key])
        self.write_class_end()

    def write_transition_forward(self, tr):
        self.write_var_struct(tr)
        self.line("bool enable_{0.id}_check(CaThread *thread, CaNet *net);", tr)

    def write_transition(self, tr):
        if tr.code is not None:
            self.write_transition_user_function(tr)
        self.write_enable(tr)
        self.write_enable_check(tr)

    def write_transition_user_function(self, tr):
        self.line("void transition_user_fn_{0.id}(CaContext &ctx, Vars_{0.id} &var)", tr)
        self.line("{{")
        self.writer.raw_text(tr.code)
        self.line("}}")

    def write_place_user_function(self, place):
        t = self.emitter.emit_type(place.type)
        self.line("void place_user_fn_{0.id}(CaContext &ctx, std::vector<{1} > &tokens)".format(place, t))
        self.line("{{")
        self.writer.raw_text(place.code)
        self.line("}}")

    def get_place_user_fn_header(self, place):
        t = self.emitter.emit_type(place.type)
        if t[-1] == ">":
            t += " "
        return "void place_fn(CaContext &ctx, std::vector<{1}> &tokens)\n{{\n".format(place, t)

    def get_transition_user_fn_header(self, transition):
        context = transition.get_context()
        w = writer.Writer()
        w.line("struct Vars {{")
        for key, value in context.items():
            w.line("\t{1} {0};", key, self.emitter.emit_type(value))
        w.line("}};")
        w.emptyline()
        w.line("void transition_fn(CaContext &ctx, Vars &vars)")
        return w.get_string()

    def get_size_code(self, t, code):
        if t == t_int:
            return "sizeof({0})".format(code)
        if t == t_string:
            return "(sizeof(size_t) + ({0}).size())".format(code)
        if t.name == "":
            return "({0}).get_mem_size()".format(code)
        raise Exception("Unknown type: " + str(t))

    def get_pack_code(self, t, packer, code):
        if t == t_int:
            return "{0}.pack_int({1});".format(packer, code)
        raise Exception("Unknown type: " + str(t))

    def get_unpack_code(self, t, unpacker):
        if t == t_int:
            return "{0}.unpack_int()".format(unpacker)
        raise Exception("Unknown type: " + str(t))

    def write_send_token(self, w, em, edge):
        if edge.target == None:
            w.line("n->place_{0.id}.add({1});", edge.get_place(), edge.expr.emit(em))
        else:
            w.line("int target_{0.id} = {1};", edge, edge.target.emit(em))
            w.line("if (target_{0.id} == thread->get_process_id()) {{", edge)
            w.indent_push()
            w.line("n->place_{0.id}.add({1});", edge.get_place(), edge.expr.emit(em))
            w.indent_pop()
            w.line("}} else {{")
            w.indent_push()
            t = edge.expr.nel_type
            w.line("{0} value = {1};", em.emit_type(t), edge.expr.emit(em))
            w.line("CaPacker packer({0});", self.get_size_code(t, "value"))
            w.line("{0};", self.get_pack_code(t, "packer", "value"))
            w.line("thread->send(target_{0.id}, net->get_id(), {1}, packer);", edge, edge.get_place().get_pos_id())
            w.indent_pop()
            w.line("}}")

    def write_enable(self, tr):
        self.line("bool enable_{0.id}(CaThread *thread, CaNet *net) {{", tr)
        self.indent_push()

        w = writer.Writer()

        for i, edge in enumerate(tr.edges_in):
            w.line("n->place_{1.id}.remove(token_{0});", i, edge.get_place())

        w.line("net->activate_transition_by_pos_id({0});", tr.get_pos_id())

        if tr.subnet is not None:
            w.line("net->unlock();")
            w.line("thread->spawn_net({0});", tr.subnet.get_index())
        else: # Without subnet
            if tr.code is not None:
                w.line("net->unlock();")
                w.line("CaContext ctx(thread);")
                w.line("transition_user_fn_{0.id}(ctx, vars);", tr)
                w.line("net->lock();")

            em = emitter.Emitter()
            em.variable_emitter = lambda name: "vars." + name

            for edge in tr.edges_out:
                self.write_send_token(w, em, edge)
            w.line("net->unlock();")
        w.line("return true;")

        self.write_enable_pattern_match(tr, w)
        self.line("return false;")
        self.block_end()

    def write_enable_check(self, tr):
        self.line("bool enable_{0.id}_check(CaThread *thread, CaNet *net) {{", tr)
        self.indent_push()

        w = writer.Writer()
        w.line("return true;")

        self.write_enable_pattern_match(tr, w)
        self.line("return false;")
        self.block_end()

    def write_enable_pattern_match(self, tr, fire_code):
        matches = get_edges_mathing(self.project, tr)
        self.line("Vars_{0.id} vars;", tr)
        self.line("Net_{0.id} *n = (Net_{0.id}*) net;", tr.net)

        em = emitter.Emitter()

        need_tokens = utils.multiset([ edge.get_place() for edge, instrs in matches ])

        for place, count in need_tokens.items():
            self.line("if (n->place_{0.id}.size() < {1}) return false;", place, count)

        em.variable_emitter = lambda name: "vars." + name

        for i, (edge, instrs) in enumerate(matches):
            place_t = self.emitter.emit_type(edge.get_place_type())
            place_id = edge.get_place().id
            token = "token_{0}".format(i)
            self.line("CaToken<{0}> *{1} = n->place_{2}.begin();", place_t, token, place_id)
            em.set_extern("token", token + "->element")
            em.set_extern("fail", "{0} = {0}->next; continue;".format(token))
            self.line("do {{")
            self.indent_push()
            for instr in instrs:
                instr.emit(em, self.writer)

        self.writer.add_writer(fire_code)

        for i, (edge, instrs) in reversed(list(enumerate(matches))):
            self.line("token_{0} = token_{0}->next;", i)
            self.indent_pop()
            self.line("}} while (token_{0} != n->place_{1.id}.begin());", i, edge.get_place())

    def build(self):
        #self.inject_types(project)
        self.project.inject_types()
        self.write_header()
        self.write_types()
        for net in self.project.nets:
            self.build_net(net)
        self.write_main()
        return self.get_writer()

    def write_spawn(self, net):
        self.line("CaNet * spawn_{0.id}(CaThread *thread, CaNetDef *def, int id) {{", net)
        self.indent_push()
        self.line("Net_{0.id} *net = new Net_{0.id}(id, id % thread->get_process_count(), def);", net)
        self.line("CaContext ctx(thread);")
        self.line("int pid = thread->get_process_id();")
        for area in net.areas:
            self.line("std::vector<int> area_{0.id} = {1};", area, area.expr.emit(self.emitter))
        for place in net.places:
            if not (place.init_expression or place.code):
                continue
            areas = place.get_areas()
            if areas == []:
                self.if_begin("pid == net->get_main_process_id()")
            else:
                conditions = [ "std::find(area_{0.id}.begin(), area_{0.id}.end(), pid)!=area_{0.id}.end()"
                              .format(area) for area in areas ]
                self.if_begin(" && ".join(conditions))
            if place.init_expression is not None:
                self.line("net->place_{0.id}.add_all({1});", place, place.init_expression.emit(self.emitter))
            if place.code is not None:
                t = self.emitter.emit_type(place.type)
                self.line("std::vector<{0}> tokens;", t)
                self.line("place_user_fn_{0.id}(ctx, tokens);", place)
                self.line("net->place_{0.id}.add_all(tokens);", place)
            self.block_end()

        self.line("return net;")
        self.indent_pop()
        self.line("}}")

    def block_begin(self):
        self.line("{{")
        self.indent_push()

    def block_end(self):
        self.indent_pop()
        self.line("}}")

    def if_begin(self, expr):
        self.line("if ({0}) {{", expr)
        self.indent_push()

    def while_begin(self, expr):
        self.line("while ({0}) {{", expr)
        self.indent_push()

    def do_begin(self):
        self.line("do {{")
        self.indent_push()

    def do_end(self, expr):
        self.indent_pop()
        self.line("}} while ({0});", expr)

    def reports_method(self, net):
        self.write_method_start("void write_reports_content(CaThread *thread, CaOutput &output)")
        for place in net.places:
            self.line('output.child("place");')
            self.line('output.set("id", {0.id});', place)
            self.block_begin()
            self.line('CaToken<{1}> *t = place_{0.id}.begin();', place, self.emitter.emit_type(place.type))
            self.if_begin("t")

            self.do_begin()
            self.line('output.child("token");')
            self.line('output.set("value", {0});', self.emitter.as_string("t->element", place.type))
            self.line('output.back();')
            self.line("t = t->next;")
            self.do_end("t != place_{0.id}.begin()".format(place))
            self.block_end()
            self.block_end()
            self.line('output.back();')
        for tr in net.transitions:
            self.line("if (enable_{0.id}_check(thread, this)) {{", tr)
            self.indent_push()
            self.line('output.child("enabled");')
            self.line('output.set("id", {0.id});', tr)
            self.line('output.back();')
            self.block_end()
        self.write_method_end()

    def receive_method(self, net):
        self.write_method_start("void receive(int place_pos, CaUnpacker &unpacker)")
        self.line("switch(place_pos) {{")
        for place in net.places:
            if any((edge.target is not None for edge in place.get_edges_in())):
                self.line("case {0}:", place.get_pos_id())
                self.indent_push()
                self.line("place_{0.id}.add({1});", place, self.get_unpack_code(place.type, "unpacker"))
                self.line("break;")
                self.indent_pop()
        self.line("}}")
        self.write_method_end()


    def build_net(self, net):

        for place in net.places:
            if place.code is not None:
                self.write_place_user_function(place)

        for tr in net.transitions:
            self.write_transition_forward(tr)

        class_name = "Net_" + str(net.id)
        self.write_class_head(class_name, "CaNet")

        self.write_constructor(class_name, [("id", "int"), ("main_process_id", "int"), ("def", "CaNetDef *")],
                               ["CaNet(id, main_process_id, def)"])
        self.write_method_end()

        for place in net.places:
            self.write_var_decl("place_" + str(place.id), t_place(place.type))

        self.reports_method(net)
        self.receive_method(net)
        self.write_class_end()

        self.write_spawn(net)

        for tr in net.transitions:
            self.write_transition(tr)

    def write_class_head(self, name, parent = None):
        if parent:
            inheritance = " : public {0} ".format(parent)
        else:
            inheritance = ""
        self.line("class {0} {1}{{", name, inheritance)
        self.indent_push()
        self.line("public:")

    def write_class_end(self):
        self.indent_pop()
        self.line("}};")

    def write_var_decl(self, name, t):
        self.line("{0} {1};", self.emitter.emit_type(t), name)

    def write_method_start(self, decl):
        self.line(decl + " {{")
        self.indent_push()

    def write_method_end(self):
        self.indent_pop()
        self.line("}}")

    def write_constructor(self, name, args, inits):
        decl = "{0}({1})".format(name, self.emitter.emit_declarations(args))
        if inits:
            decl += " : " + ",".join(inits)
        self.write_method_start(decl)
