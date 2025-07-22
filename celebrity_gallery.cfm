<cfinclude template="head.cfm">

<style>
.celeb-image {
  object-fit: cover;
  object-position: top;
  height: 220px;
  width: 100%;
  transition: transform 0.3s ease;
}

.celeb-image:hover {
  transform: scale(1.05);
}

.card {
  transition: transform 0.3s ease;
}

.hover-scale:hover {
  transform: scale(1.02);
}
</style>

<cfinclude template="navbar.cfm">

<div class="container mt-4">
  <h2 class="mb-4">Celebrity Gallery</h2>

  <!--- Search and Toggle Buttons --->
  <div class="row mb-4">
    <div class="col-md-6">
      <input type="text" id="celebritySearch" class="form-control" placeholder="Search celebrities...">
    </div>
<div class="col-md-6 text-end">
  <button id="toggleVerified" class="btn btn-outline-secondary me-2">Verified</button>
  <button id="toggleCourtLinked" class="btn btn-outline-secondary">Court Cases</button>
</div>

  </div>

  <!--- Celebrity Cards --->
  <div id="celebrityGallery" class="row"></div>

  <!--- Modal (no longer used but keeping for potential future) --->
  <div class="modal fade" id="celebrityModal" tabindex="-1" aria-labelledby="celebrityModalLabel" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="celebrityModalLabel">Celebrity Details</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body" id="celebrityModalBody">
          <!--- Filled dynamically --->
        </div>
      </div>
    </div>
  </div>
</div>

<script>
var allCelebrities = [];
var verifiedOnly = false;
var courtLinkedOnly = false;
var currentPage = 1;
var itemsPerPage = 12;

function loadCelebrities() {
  fetch('celeb_gallery_ajax.cfm')
    .then(response => response.json())
    .then(data => {
      allCelebrities = data;
      renderGallery();
    })
    .catch(error => console.error('Error loading celebrities:', error));
}

var initialLoad = true; // 🚀 Add this variable at the top of your script

function renderGallery() {
  var search = document.getElementById('celebritySearch').value.toLowerCase();
  var gallery = document.getElementById('celebrityGallery');
  gallery.innerHTML = '';

  var filtered = allCelebrities.filter(c => {
    if (verifiedOnly && !c.verified) return false;
    if (courtLinkedOnly && (!c.caseCount || c.caseCount == 0)) return false;
    if (search && !(c.name_search && c.name_search.toLowerCase().includes(search))) return false;
    return true;
  });

  var totalPages = Math.ceil(filtered.length / itemsPerPage);
  if (currentPage > totalPages) currentPage = totalPages;

  var start = (currentPage - 1) * itemsPerPage;
  var end = start + itemsPerPage;
  var paginated = filtered.slice(start, end);

  paginated.forEach(c => {
    var col = document.createElement('div');
    col.className = 'col-6 col-sm-4 col-md-3 col-lg-2 mb-4';
    col.innerHTML = `
      <a href="celebrity_details.cfm?id=${c.id}" style="text-decoration: none; color: inherit;">
        <div class="card h-100 shadow-sm rounded ${initialLoad ? 'animate__animated animate__fadeIn' : ''} hover-scale">
          <img 
            src="../services/avatar_placeholder.png" 
            data-wikiid="${c.wikiId}" 
            class="card-img-top celeb-image" 
            alt="${c.name}">
          <div class="card-body d-flex flex-column justify-content-between">
  <div>
<div class="card-title fw-semibold" style="font-size: 0.85rem;">
  ${c.name} ${c.verified ? '<i class="fas fa-check-circle text-primary ms-1"></i>' : ''}
</div>
  </div>
  <div class="d-flex flex-wrap justify-content-between align-items-center mt-2">
    ${getPriorityBadge(c.priorityScore)}
    ${getRelevancyBadge(c.relevancyIndex)}
  </div>
</div>

        </div>
      </a>
    `;
    gallery.appendChild(col);
  });

  renderPagination(totalPages);
  fetchWikidataImages();

  initialLoad = false; // 🔥 After first full render, disable animation for future redraws
}


function renderPagination(totalPages) {
  var gallery = document.getElementById('celebrityGallery');
  var paginationRow = document.createElement('div');
  paginationRow.className = 'row mt-2 justify-content-center';

  const maxPagesToShow = 10; // First + last + 5 dynamic pages
  const buffer = 2; // How many pages to show before/after current

  let pagination = `<nav><ul class="pagination">`;

  // Previous button
  pagination += `
    <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
      <button class="page-link" onclick="changePage(${currentPage - 1})">&laquo;</button>
    </li>
  `;

  // First page
  if (currentPage > buffer + 2) {
    pagination += `
      <li class="page-item"><button class="page-link" onclick="changePage(1)">1</button></li>
      <li class="page-item disabled"><span class="page-link">...</span></li>
    `;
  }

  // Dynamic middle pages
  const startPage = Math.max(1, currentPage - buffer);
  const endPage = Math.min(totalPages, currentPage + buffer);
  for (let i = startPage; i <= endPage; i++) {
    pagination += `
      <li class="page-item ${currentPage === i ? 'active' : ''}">
        <button class="page-link" onclick="changePage(${i})">${i}</button>
      </li>
    `;
  }

  // Last page
  if (currentPage < totalPages - (buffer + 1)) {
    pagination += `
      <li class="page-item disabled"><span class="page-link">...</span></li>
      <li class="page-item"><button class="page-link" onclick="changePage(${totalPages})">${totalPages}</button></li>
    `;
  }

  // Next button
  pagination += `
    <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
      <button class="page-link" onclick="changePage(${currentPage + 1})">&raquo;</button>
    </li>
  `;

  pagination += `</ul></nav>`;
  paginationRow.innerHTML = pagination;
  gallery.appendChild(paginationRow);
}


function changePage(page) {
  currentPage = page;
  renderGallery();
}

function fetchWikidataImages() {
  document.querySelectorAll('.celeb-image').forEach(img => {
    var wikiId = img.getAttribute('data-wikiid');
    if (wikiId) {
      fetch('https://www.wikidata.org/wiki/Special:EntityData/' + wikiId + '.json')
        .then(response => response.json())
        .then(data => {
          try {
            var entities = data.entities;
            var entity = entities[wikiId];
            var claims = entity.claims;
            var p18 = claims.P18[0].mainsnak.datavalue.value;
            var fileName = encodeURIComponent(p18);
            var imageUrl = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + fileName;
            img.setAttribute('src', imageUrl);
          } catch (error) {
            console.log('No image found for', wikiId);
          }
        })
        .catch(error => console.error('Error loading image for', wikiId, error));
    }
  });
}

// Priority badge
function getPriorityBadge(score) {
  if (score >= 8) {
    return '<span class="badge bg-danger"><i class="fas fa-fire"></i> Top Priority</span>';
  } else if (score >= 4) {
    return '<span class="badge bg-warning text-dark"><i class="fas fa-star"></i> Mid Priority</span>';
  } else {
    return '<span class="badge bg-primary"><i class="fas fa-feather-alt"></i> Low Priority</span>';
  }
}

// Relevancy badge
function getRelevancyBadge(index) {
  if (index >= 8) {
    return '<span class="badge bg-success">Top Relevancy</span>';
  } else if (index >= 4) {
    return '<span class="badge bg-warning text-dark">Mid Relevancy</span>';
  } else {
    return '<span class="badge bg-secondary">Low Relevancy</span>';
  }
}

// Search and toggle event listeners
document.getElementById('celebritySearch').addEventListener('input', function() {
  currentPage = 1;
  renderGallery();
});

document.getElementById('toggleVerified').addEventListener('click', function() {
  verifiedOnly = !verifiedOnly;
  if (verifiedOnly) {
    this.classList.remove('btn-outline-secondary');
    this.classList.add('btn-primary');
  } else {
    this.classList.remove('btn-primary');
    this.classList.add('btn-outline-secondary');
  }
  currentPage = 1;
  renderGallery();
});

document.getElementById('toggleCourtLinked').addEventListener('click', function() {
  courtLinkedOnly = !courtLinkedOnly;
  if (courtLinkedOnly) {
    this.classList.remove('btn-outline-secondary');
    this.classList.add('btn-success');
  } else {
    this.classList.remove('btn-success');
    this.classList.add('btn-outline-secondary');
  }
  currentPage = 1;
  renderGallery();
});


// Load
loadCelebrities();
</script>

<cfinclude template="footer_script.cfm">
