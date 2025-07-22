<cfset defaultID = "D8907F61-40C5-4D60-ACEF-0B7721A293B3">
<cfparam name="url.id" default="#defaultID#">

<cfquery name="celeb" datasource="reach">
SELECT 
    c.id,
    c.name as celebrity_name,
    COALESCE(e.external_id, '') as wikidata_id 
FROM docketwatch.dbo.celebrities c
left JOIN docketwatch.dbo.celebrity_external_links e ON e.fk_celebrity = c.id
WHERE  c.id = <cfqueryparam value="#url.id#" cfsqltype="cf_sql_varchar"> 
</cfquery>

<cfquery name="aliases" datasource="reach">
    SELECT name as alias_name, type, source
    FROM docketwatch.dbo.celebrity_names
    WHERE fk_celebrity = <cfqueryparam value="#celeb.id#" cfsqltype="cf_sql_varchar">

    ORDER BY type desc, alias_name
</cfquery>

<cfquery name="qAliases" datasource="reach">
  SELECT 
    name AS alias_name, 
    type, 
    source
  FROM docketwatch.dbo.celebrity_names
  WHERE fk_celebrity = <cfqueryparam value="#celeb.id#" cfsqltype="cf_sql_varchar">
    AND isprimary = 0
  ORDER BY 
    type DESC, 
    alias_name ASC
</cfquery>


<cfset aliasList = []>
<cfoutput query="aliases">
    <cfset label = "">
    <cfif type EQ "birth">
        <cfset label = " (Birth)">
    <cfelseif type EQ "legal">
        <cfset label = " (Legal)">
    <cfelse>
    <cfset label = "" />
    </cfif>

    <cfset nameDisplay = alias_name & label>

    <cfif len(trim(source)) and source neq "Wikidata">
        <cfset nameDisplay &= ' <i class="fa fa-circle-info text-muted ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="' & htmlEditFormat(source) & '"></i>'>
    </cfif>

    <cfset arrayAppend(aliasList, nameDisplay)>
</cfoutput>




<!--- Only do Wikidata logic if we have a valid ID --->
<cfset celebID = trim(celeb.wikidata_id)>
<cfif len(celebID)>
    <cfhttp url="https://www.wikidata.org/wiki/Special:EntityData/#celebID#.json" method="get" result="wikidataResponse" timeout="10"></cfhttp>
    <cfset wikidata = deserializeJSON(wikidataResponse.fileContent)>
    <cfset entity = structKeyExists(wikidata.entities, celebID) ? wikidata.entities[celebID] : {}>

    <!--- Description --->
    <cfset description = "">
    <cfif structKeyExists(entity, "descriptions") AND structKeyExists(entity.descriptions, "en")>
        <cfset description = entity.descriptions["en"].value>
    </cfif>

    <!--- Profile Picture --->
    <cfset profilePic = "../services/avatar_placeholder.png">
    <cfif structKeyExists(entity, "claims") AND structKeyExists(entity.claims, "P18")>
        <cfset imageFilename = entity.claims.P18[1].mainsnak.datavalue.value>
        <cfset encodedName = replace(imageFilename, " ", "_", "all")>
        <cfset profilePic = "https://commons.wikimedia.org/wiki/Special:FilePath/" & encodedName & "?width=400">
    </cfif>

    <!--- Roles --->
    <cfset roles = []>
    <cfif structKeyExists(entity, "claims") AND structKeyExists(entity.claims, "P106")>
        <cfloop array="#entity.claims.P106#" index="roleItem">
            <cfif structKeyExists(roleItem.mainsnak, "datavalue") 
                AND structKeyExists(roleItem.mainsnak.datavalue, "value")
                AND isStruct(roleItem.mainsnak.datavalue.value)
                AND structKeyExists(roleItem.mainsnak.datavalue.value, "id")>

                <cfset roleId = roleItem.mainsnak.datavalue.value.id>
                <cfhttp url="https://www.wikidata.org/wiki/Special:EntityData/#roleId#.json" method="GET" result="roleResponse" timeout="5"></cfhttp>

                <cfif roleResponse.statusCode eq "200 OK">
                    <cfset roleData = deserializeJSON(roleResponse.filecontent)>
                    <cfif structKeyExists(roleData, "entities") 
                        and structKeyExists(roleData.entities, roleId)
                        and structKeyExists(roleData.entities[roleId], "labels")
                        and structKeyExists(roleData.entities[roleId].labels, "en")>
                        <cfset arrayAppend(roles, roleData.entities[roleId].labels.en.value)>
                    </cfif>
                </cfif>
            </cfif>
        </cfloop>
    </cfif>
<cfelse>
    <!--- No wikidata_id: fallback values --->
    <cfset description = "">
    <cfset profilePic = "../services/avatar_placeholder.png">
    <cfset roles = []>
</cfif>



<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><cfoutput>#celeb.celebrity_name# - Celebrity Profile</cfoutput></title>
  <cfinclude template="head.cfm">
  <style>
    .avatar-img {
      width: 200px;
      height: 200px;
      object-fit: cover;
      border-radius: 50%;
    }
  </style>
</head>
<body>
  <cfinclude template="navbar.cfm">

  <div class="container mt-4">
    <cfoutput>
    <div class="card shadow-sm mb-4">
      <div class="card-body">
        <div class="d-flex align-items-center mb-3">
          <img src="#profilePic#" class="avatar-img me-3" alt="#celeb.celebrity_name#">
          <div>
            <h4 class="card-title mb-0">#celeb.celebrity_name#</h4>
            <cfif len(trim(description))>
              <small class="text-muted">#description#</small>
            </cfif>
          </div>
        </div>
        
<cfif arrayLen(aliasList)>
  <p><strong>Also Known As:</strong> #arrayToList(aliasList, " | ")#</p>
</cfif>


        <cfif arrayLen(roles)>
          <p><strong>Roles:</strong> #arrayToList(roles, " | ")#</p>
        </cfif>

        <p><strong>Wikidata ID:</strong> <a href="https://www.wikidata.org/wiki/#celeb.wikidata_id#" target="_blank">#celeb.wikidata_id#</a></p>
      </div>
    </div>
    </cfoutput>







<!--- Tabs Navigation --->
<ul class="nav nav-tabs mt-4" id="celebTabs" role="tablist">
  <li class="nav-item" role="presentation">
    <button class="nav-link active" id="cases-tab" data-bs-toggle="tab" data-bs-target="#cases" type="button" role="tab">Cases</button>
  </li>
  <li class="nav-item" role="presentation">
    <button class="nav-link" id="names-tab" data-bs-toggle="tab" data-bs-target="#names" type="button" role="tab">Names</button>
  </li>
  <li class="nav-item" role="presentation">
    <button class="nav-link" id="log-tab" data-bs-toggle="tab" data-bs-target="#log" type="button" role="tab">Log</button>
  </li>
</ul>

<!--- Tab Content --->
<div class="tab-content border rounded-bottom p-3 bg-white" id="celebTabsContent">
  <div class="tab-pane fade show active" id="cases" role="tabpanel" aria-labelledby="cases-tab">
    <!--- TODO: Case matches will go here --->
    <p class="text-muted">Linked cases will appear here.</p>
  </div>
  <div class="tab-pane fade" id="names" role="tabpanel" aria-labelledby="names-tab">
    <!--- Aliases Table --->
<table class="table table-bordered table-striped mt-3">
  <thead class="table-light">
    <tr>
      <th width="5%">Action</th>
      <th>Name</th>
      <th>Type</th>
      <th>Source</th>
    </tr>
  </thead>
  <tbody>
    <cfoutput query="qAliases">
      <tr>
        <td>
          <button class="btn btn-sm btn-outline-primary" title="Edit Alias">
            <i class="fas fa-edit"></i>
          </button>
        </td>
        <td>#encodeForHTML(alias_name)#</td>
        <td>#encodeForHTML(type)#</td>
        <td>#encodeForHTML(source)#</td>
      </tr>
    </cfoutput>
  </tbody>
</table>

    <p class="text-muted">Alternate names for this celebrity will appear here.</p>
  </div>
  <div class="tab-pane fade" id="log" role="tabpanel" aria-labelledby="log-tab">
    <!--- TODO: System logs --->
    <p class="text-muted">System update logs will appear here.</p>
  </div>
</div>


  </div>













  <script>
document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
</script>


  <cfinclude template="footer_script.cfm">
</body>
</html>
