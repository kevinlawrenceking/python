 select doc_uid, isfound,        'http://docketwatch.tmz.local/docs/cases/' + 
            CAST(d.fk_case AS VARCHAR) + '/E' + 
            CAST(d.doc_id AS VARCHAR) + '.pdf' AS http_url

			from documents d where isfound = 0
