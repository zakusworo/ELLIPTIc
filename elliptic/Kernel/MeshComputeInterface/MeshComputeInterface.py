import os
import tempfile

from jinja2 import Environment, PackageLoader

from .DynamicCompiler.utils import (build_extension, elliptic_cythonize,
                                    import_extension)


class TemplateManager:

    jinja2_env = Environment(loader=PackageLoader(__package__, 'Templates'))

    def get_template(self, template_file):
        return self.jinja2_env.get_template(template_file)

    def render(self, template_file, **kwargs):
        template = self.get_template(template_file)
        return template.render(**kwargs)


class ContextNode:

    # Overwrite for extending with your own templates
    template_manager = TemplateManager()

    def __init__(self, parent):
        self._template_file = ""
        self._template_args = {}
        self._parent = parent
        self._child_templates = []

        self.child_nodes = []

    def set_template_file(self, template_file):
        self._template_file = template_file

    def set_options(self, **kwargs):
        self._template_args.update(kwargs)

    def _add_child_template(self, child_template):
        self._child_templates.append(child_template)

    def add_child_node(self, child_node):
        self.child_nodes.append(child_node)

    def _render(self):
        kwargs = self._template_args

        return self.template_manager.render(template_file=self._template_file,
                                            child=self._child_templates,
                                            **kwargs)


class Context:

    build_dir_prefix = 'elliptic__'
    base_template = 'base.pyx.etp'
    template_manager = TemplateManager()

    def __init__(self):
        self.built_module = None
        self.context_root = None

    def set_context_root(self, root):
        self.context_root = root

    def compile_tree(self):
        cython_dir = tempfile.mkdtemp(prefix=self.build_dir_prefix)
        module_fd, module_path = tempfile.mkstemp(
            suffix='.pyx', dir=cython_dir)

        module_name = module_path.split('/')[-1].strip('.pyx')

        full_rendered_template = self._render_tree()

        with os.fdopen(module_fd, 'w') as f:
            f.write(full_rendered_template)

        extensions = elliptic_cythonize(module_name, module_path)

        built_ext = build_extension(extensions[0], cython_dir)
        ext_path = built_ext.get_ext_fullpath(module_name)

        self.built_module = import_extension(module_name, ext_path)

        return self.built_module

    def __render_tree_rec(self, context_node):
        for child in context_node.child_nodes:
            rendered_template = self.__render_tree_rec(child)
            context_node._add_child_template(rendered_template)

        return context_node._render()

    def _render_tree(self):
        rendered_tree = self.__render_tree_rec(self.context_root)

        rendered_base = self.template_manager.render(self.base_template,
                                                     child=rendered_tree)

        return rendered_base


class MeshComputeInterface:

    def __init__(self, context_class):
        if not context_class:
            self.context = Context()
        else:
            self.context = context_class()

    def selector(self, selector_class=None):
        if not selector_class:
            from .Selector import EntitySelector
            selector_class = EntitySelector

        selector_obj = selector_class(parent=None)

        self.context.set_context_root(selector_obj._get_context_node())

        return selector_obj

    def _build_context(self):
        return self.context.compile_tree()
