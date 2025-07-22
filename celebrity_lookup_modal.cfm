<!--- Celebrity Lookup Modal --->
<div class="modal fade" id="celebrityLookupModal" tabindex="-1" aria-labelledby="celebrityLookupLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="celebrityLookupLabel">Select or Add Celebrity</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div id="searchModeInstructions">
          <p>Start typing to select a celebrity from the database.</p>
        </div>

 
<div id="celebritySelectWrapper" class="position-relative">
  <select id="celebritySearch" style="width: 100%;"></select>
</div>
        <input type="hidden" id="celebrityId">

        <div id="celebrityWarnings" class="mt-3" style="display: none;">
          <div id="primaryNotice" class="alert alert-info" style="display: none;"></div>
          <div id="verifyWarning" class="alert alert-warning" style="display: none;"></div>
        </div>

        <div id="newCelebrityNotice" class="alert alert-success mt-3" style="display: none;">
          We’ll create a new unverified entry for <strong id="newNameText"></strong>.
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-primary" id="submitCelebrityBtn" style="display:none;">Select Celebrity</button>
      </div>
    </div>
  </div>
</div>



