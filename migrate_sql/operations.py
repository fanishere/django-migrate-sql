from django.db.migrations.operations import RunSQL
from django.db.migrations.operations.base import Operation

from migrate_sql.graph import SQLStateGraph
from migrate_sql import SQLItem


class MigrateSQLMixin(object):
    def get_sql_config(self, state):
        if not hasattr(state, 'sql_config'):
            setattr(state, 'sql_config', SQLStateGraph())
        return state.sql_config


class AlterSQLState(MigrateSQLMixin, Operation):
    def describe(self):
        return 'Alter SQL state "{name}"'.format(name=self.name)

    def deconstruct(self):
        kwargs = {
            'name': self.name,
        }
        if self.add_dependencies:
            kwargs['add_dependencies'] = self.add_dependencies
        if self.remove_dependencies:
            kwargs['remove_dependencies'] = self.remove_dependencies
        return (self.__class__.__name__, [], kwargs)

    def state_forwards(self, app_label, state):
        sql_config = self.get_sql_config(state)
        key = (app_label, self.name)

        if key not in sql_config.nodes:
            # XXX: dummy for `migrate` command, that does not preserve state object.
            # Should fail with error when fixed.
            return

        sql_item = sql_config.nodes[key]

        for dep in self.add_dependencies:
            # we are also adding relations to aggregated SQLItem, but only to restore
            # original items. Still using graph for advanced node/arc manipulations.

            # XXX: dummy `if` for `migrate` command, that does not preserve state object.
            # Fail with error when fixed
            if dep in sql_item.dependencies:
                sql_item.dependencies.remove(dep)
            sql_config.add_lazy_dependency(key, dep)

        for dep in self.remove_dependencies:
            sql_item.dependencies.append(dep)
            sql_config.remove_lazy_dependency(key, dep)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass

    @property
    def reversible(self):
        return True

    def __init__(self, name, add_dependencies=None, remove_dependencies=None):
        self.name = name
        self.add_dependencies = add_dependencies or ()
        self.remove_dependencies = remove_dependencies or ()


class BaseAlterSQL(MigrateSQLMixin, RunSQL):
    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None):
        super(BaseAlterSQL, self).__init__(sql, reverse_sql=reverse_sql,
                                           state_operations=state_operations, hints=hints)
        self.name = name

    def deconstruct(self):
        name, args, kwargs = super(BaseAlterSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)


class ReverseAlterSQL(BaseAlterSQL):
    def describe(self):
        return 'Reverse alter SQL "{name}"'.format(name=self.name)


class AlterSQL(BaseAlterSQL):
    def deconstruct(self):
        name, args, kwargs = super(AlterSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)

    def describe(self):
        return 'Alter SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(AlterSQL, self).state_forwards(app_label, state)
        sql_config = self.get_sql_config(state)
        key = (app_label, self.name)

        if key not in sql_config.nodes:
            # XXX: dummy for `migrate` command, that does not preserve state object.
            # Fail with error when fixed
            return

        sql_item = sql_config.nodes[key]
        sql_item.sql = self.sql
        sql_item.reverse_sql = self.reverse_sql


class CreateSQL(BaseAlterSQL):
    def describe(self):
        return 'Create SQL "{name}"'.format(name=self.name)

    def deconstruct(self):
        name, args, kwargs = super(CreateSQL, self).deconstruct()
        kwargs['name'] = self.name
        if self.dependencies:
            kwargs['dependencies'] = self.dependencies
        return (name, args, kwargs)

    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None,
                 dependencies=None):
        super(CreateSQL, self).__init__(name, sql, reverse_sql=reverse_sql,
                                        state_operations=state_operations, hints=hints)
        self.dependencies = dependencies or ()

    def state_forwards(self, app_label, state):
        super(CreateSQL, self).state_forwards(app_label, state)
        sql_config = self.get_sql_config(state)

        sql_config.add_node(
            (app_label, self.name),
            SQLItem(self.name, self.sql, self.reverse_sql, list(self.dependencies)),
        )

        for dep in self.dependencies:
            sql_config.add_lazy_dependency((app_label, self.name), dep)


class DeleteSQL(BaseAlterSQL):
    def describe(self):
        return 'Delete SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(DeleteSQL, self).state_forwards(app_label, state)
        sql_config = self.get_sql_config(state)

        sql_config.remove_node((app_label, self.name))
        sql_config.remove_lazy_for_child((app_label, self.name))
