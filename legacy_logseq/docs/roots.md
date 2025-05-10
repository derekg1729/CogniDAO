# Cogni Roots
::tags: #roots

## About Roots
Roots represent completed projects that form the foundation of our work. These are stable, working components that can be built upon.

## Completed Projects
The following projects have been completed and form our roots:

#+BEGIN_QUERY
{:title "Completed Projects"
 :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "done"]]}
#+END_QUERY

## Structure
- Each completed project maintains its original file structure:
  - `project:[name].md`
  - Properties: `:status: done` `:epic:` `:owner:`

## Organization
Projects are organized by their parent epic.

