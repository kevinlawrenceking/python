<!--- Bootstrap 5 CSS --->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

<!--- DataTables CSS (Bootstrap 5 integration) --->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">

<!--- Font Awesome --->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">

<!--- Animate.css --->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">

<!--- jQuery (must come first) --->
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

<link rel="stylesheet" href="https://code.jquery.com/ui/1.13.2/themes/base/jquery-ui.css"> 

<!--- Select2 CSS --->
<link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />

<!--- SweetAlert2 --->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

<!--- Select2 (requires jQuery) --->
<script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>



<!--- Custom Styling --->
<style>
.description-column {
    min-width: 500px !important; /* Enforces the minimum width */
    width: 500px !important;     /* Sets the default width */
}
  .navbar-dark .navbar-nav .nav-link,
  .navbar-brand {
    color: white !important;
  }

  .navbar-dark .navbar-nav .nav-link.active,
  .navbar-dark .navbar-nav .nav-link.show .navbar-brand {
    color: white !important;
  }

  .dropdown-item {
    color: black !important;
  }

  .navbar-brand {
    color: #cf0000 !important;
    font-weight: 500;
  }

  .card:hover .celeb-image {
    transform: scale(1.05);
  }

  .celeb-card {
    transition: opacity 0.2s ease;
  }

  .highlighted-celeb {
    font-weight: bold;
    color: red;
  }

  @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600&family=Roboto:wght@400;700&family=Roboto+Condensed:wght@400;700&display=swap');

  body {
    font-family: "Source Sans Pro", Roboto, "Helvetica Neue", Arial, sans-serif,
      "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
  }

  h1, h2, h3, h4, h5, sorting, h6, .navbar-brand {
    font-family: "ProximaNovaExCn_Black", Impact, "Roboto Condensed", "Arial Narrow", sans-serif;
  }

  .nowrap {
    white-space: nowrap;
  }

  .select-checkbox {
    cursor: pointer;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
    padding: 5px;
  }

  .celeb-image {
  object-fit: cover;
  object-position: top;
  height: 215px;
  width: 100%;
  transition: transform 0.3s ease;
}

.celeb-image:hover {
  transform: scale(1.05);
}

.card-other {
  transition: transform 0.3s ease;
}

.card-other:hover {
  transform: scale(1.02);
}
 
  ::placeholder {
    color: #aaa !important;
    opacity: 1; /* Needed for Firefox */
  }
</style>

