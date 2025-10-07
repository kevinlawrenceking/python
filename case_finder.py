 select doc_uid, isfound,        'https://docketwatch.tmz.tv/docs/cases/' + 
            CAST(d.fk_case AS VARCHAR) + '/E' + 
            CAST(d.doc_id AS VARCHAR) + '.pdf' AS http_url

			from documents d where isfound = 0
