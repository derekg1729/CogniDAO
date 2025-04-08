#+BEGIN_QUERY
{:title "Open Tasks (by Project)"
 :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?p]
         [(get ?p :status) "in_progress"]
         [(get ?p :project) "infra-core"]]}
#+END_QUERY
