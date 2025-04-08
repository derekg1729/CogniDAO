# CogniDAO Core Infrastructure
:owner: CogniDAO
- ## Description
  Core infrastructure for Cogni-based projects: tooling, data structures, AI orchestrations, and DAO ops definitions that self-enable and will enable future spinoff DAOs.
- ## Navigation
  [[roadmap]] - see what we will grow
  [[roots]] - see what we have already grown
- ## Queries
- ## Epics
  #+BEGIN_QUERY
  {:title "In-Progress Projects"
  :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "in_progress"]
         [(get ?p :epic) "infra-core"]]}
  #+END_QUERY
- ## Active Projects
  #+BEGIN_QUERY
  {:title "In-Progress Projects"
  :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "in_progress"]
         [(get ?p :epic) "infra-core"]]}
  #+END_QUERY
- ## Completed Projects
  #+BEGIN_QUERY
  {:title "Completed Projects"
  :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "done"]
         [(get ?p :epic) "infra-core"]]}
  #+END_QUERY
- ## All Tasks
  #+BEGIN_QUERY
  {:title "All Tasks"
  :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :type) "Task"]]}
  #+END_QUERY