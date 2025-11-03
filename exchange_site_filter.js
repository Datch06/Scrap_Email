"use strict";

paginationInit();
// $('#exchange_site_filter_search_query').on('input', function (key) {
//     getCopywritingSites(this.value, 1, function() {
//         paginationInit();
//         $('.footable').footable(footableConfig);
//     });
// });

function getCopywritingSites(query, page, callback, params) {
    page = page === undefined ? 1 : page

    params.query = query;
    params.page = page;

    $('#exchange_sites_collection').load(
        Routing.generate('admin_exchange_site'),params
        , callback
    );
}

function changePage(page) {
    const params = Object.fromEntries(new URLSearchParams(location.search));
    var query = $('#exchange_site_filter_search_query').val();
    getCopywritingSites(query, page, function() {
      $('.footable').footable(footableConfig);
    }, params);
}

function paginationInit() {
    var pagerfanta = $('.pagerfanta');
    if(pagerfanta.html()){
        pagerfanta.twbsPagination('destroy');
    }
    if(countResults > 0) {
        var totalPages = Math.ceil(countResults / maxPerPage);
        var trans = translations;
        pagerfanta.twbsPagination({
            totalPages: totalPages,
            visiblePages: 5,
            prev: trans.name.prev,
            next: trans.name.next,
            initiateStartPageClick: false,
            startPage: 1,
            first: '<<',
            last: '>>',
            onPageClick: function onPageClick(event, page) {
                changePage(page);
            }
        });
    }
}

$(document).ready(function() {

    $(document).on('click', '.multiple-action', function(e) {
        var link = $(this).attr('href');
        var action = $(this).attr('id') === 'delete_selected' ? 'delete' : 'deactivate';
        var count = $(this).data('count');
        e.preventDefault();
        swal({
            title: 'Are you sure?',
            text: "You going to " + action + " " + count + " site(s)",
            type: "warning",
            showCancelButton: true,
            closeOnConfirm: false
        }, function(isConfirm) {
            if (isConfirm) {
                window.location.href = link;
            } else {
                return false;
            }
        });
    });

    $(document).on('change', '#selectall', function() {
        var isChecked = $(this).prop('checked');
        $('.check-list.multicheckbox input[type="checkbox"]').prop('checked', isChecked);
        updateMultipleLinks();
    });

    $(document).on('change', '.check-list.multicheckbox input[type="checkbox"]', function() {
        updateMultipleLinks();
    });

    function updateMultipleLinks() {
        var deleteLink = $('#delete_selected');
        var deactivateLink = $('#deactivate_selected');
        var selectedItems = [];
        $('.check-list.multicheckbox input[type="checkbox"]:checked').each(function() {
            selectedItems.push($(this).val());
        });

        if ($('#selectall').prop('checked')) {
            selectedItems = 'all';
        }

        if (selectedItems.length > 0) {
            var filters =  {'sites': selectedItems};

            if (selectedItems === 'all') {
                const params = new URLSearchParams(window.location.search);

                for (const [key, value] of params.entries()) {
                    filters[key] = value;
                }
            }
            filters['action'] = 'delete';
            var delHref = Routing.generate('user_multiple_action', filters);
            filters['action'] = 'deactivate';
            var deactHref = Routing.generate('user_multiple_action', filters);

            deleteLink.data('count', selectedItems === 'all' ? 'all' : selectedItems.length);
            deactivateLink.data('count', selectedItems === 'all' ? 'all' : selectedItems.length);
            deleteLink.attr('href', delHref).removeClass('disabled');
            deactivateLink.attr('href', deactHref).removeClass('disabled');
        } else {
            deleteLink.attr('href', '#').addClass('disabled');
            deactivateLink.attr('href', '#').addClass('disabled');
        }
    }

    updateMultipleLinks(); // Initialize on page load
});
