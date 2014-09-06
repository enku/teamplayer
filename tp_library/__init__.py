from django.apps import AppConfig


class TPLibraryConfig(AppConfig):
    name = 'tp_library'
    label = 'tp_library'
    verbose_name = 'TeamPlayer Library'

default_app_config = 'tp_library.TPLibraryConfig'
