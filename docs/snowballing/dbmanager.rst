dbmanager.py
=============================

.. automodule:: snowballing.dbmanager

------------------
Relevant functions
------------------


insert
-----------------------------

.. autofunction:: snowballing.dbmanager.insert


set_attribute
-----------------------------

.. autofunction:: snowballing.dbmanager.set_attribute


rename_work
-----------------------------

.. autofunction:: snowballing.dbmanager.rename_work


insert_work
-----------------------------

.. autofunction:: snowballing.dbmanager.insert_work


insert_citation
-----------------------------

.. autofunction:: snowballing.dbmanager.insert_citation


remove_target_citation
-----------------------------

.. autofunction:: snowballing.dbmanager.remove_target_citation


remove_source_citation
-----------------------------

.. autofunction:: snowballing.dbmanager.remove_source_citation


------------------
Other Functions
------------------

rename_lines
-----------------------------

.. autofunction:: snowballing.dbmanager.rename_lines


rename_citation
-----------------------------

.. autofunction:: snowballing.dbmanager.rename_citation


citation_operation
-----------------------------

.. autofunction:: snowballing.dbmanager.citation_operation


work_operation
-----------------------------

.. autofunction:: snowballing.dbmanager.work_operation


save_lines
-----------------------------

.. autofunction:: snowballing.dbmanager.save_lines


read_file
-----------------------------

.. autofunction:: snowballing.dbmanager.read_file


is_assign_to_name
-----------------------------

.. autofunction:: snowballing.dbmanager.is_assign_to_name


is_call_statement
-----------------------------

.. autofunction:: snowballing.dbmanager.is_call_statement


------------------
Operation classes
------------------


ReplaceOperation
-----------------------------

.. autoclass:: snowballing.dbmanager.ReplaceOperation
    :members:
    :undoc-members:
    :show-inheritance:


DelOperation
-----------------------------

.. autoclass:: snowballing.dbmanager.DelOperation
    :members:
    :undoc-members:
    :show-inheritance:


AddKeywordOperation
-----------------------------

.. autoclass:: snowballing.dbmanager.AddKeywordOperation
    :members:
    :undoc-members:
    :show-inheritance:


InsertOperation
-----------------------------

.. autoclass:: snowballing.dbmanager.InsertOperation
    :members:
    :undoc-members:
    :show-inheritance:


DetectOperation
-----------------------------

.. autoclass:: snowballing.dbmanager.DetectOperation
    :members:
    :undoc-members:
    :show-inheritance:


------------------
Visitor classes
------------------


EditVisitor
-----------------------------

.. autoclass:: snowballing.dbmanager.EditVisitor
    :members:
    :undoc-members:
    :show-inheritance:


BodyVisitor
-----------------------------

.. autoclass:: snowballing.dbmanager.BodyVisitor
    :members:
    :undoc-members:
    :show-inheritance:


CitationVisitor
-----------------------------

.. autoclass:: snowballing.dbmanager.CitationVisitor
    :members:
    :undoc-members:
    :show-inheritance:

