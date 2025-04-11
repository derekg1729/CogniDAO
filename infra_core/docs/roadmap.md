# Cogni Roadmap
- ## Structure & Formatting
- **Epic**: Big vision initiatives (months/quarters)
	- Format: `epic:[name].md`
	- Properties: `:status:` `:owner:`
- **Project**: Multi-step deliverables (days/weeks)
	- Format: `project:[name].md`
	- Properties: `:status:` `:epic:` `:owner:`
- **Task**: Granular actions (hours/days)
	- Format: `task:[name].md`
	- Properties: `:status:` `:project:` `:owner:`
- ## Status Options
- `todo`
- `in_progress`
- `needs_review`
- `done`
- ## Epics
  [[Epic_Broadcast_and_Attract]]
  [[Epic_DAO_Core_Protocol]]
  [[Epic_DAO_Spawning_Grounds]]
  [[Epic_Distributed_Resilience]]
  [[Epic_Presence_and_Control_Loops]]
  [[Epic_Reflexive_Git]]
  [[Epic_System_Refinement]]
  [[Epic_Valuation_Engine]]
- ## Active Projects
  The following projects are currently in progress:
  
  #+BEGIN_QUERY
  {:title "In-Progress Projects"
  :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "in_progress"]]}
  #+END_QUERY
