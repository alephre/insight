$(document).ready( function () {
    var dt_options = {
        "language": {
            "paginate": {
                "previous": '<i class="fas fa-angle-left"></i>',
                "next": '<i class="fas fa-angle-right"></i>'
            }
        }
    };
    $('.data-table').dataTable(dt_options);

} );
