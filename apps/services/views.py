from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .selectors import active_branch_services, search_branch_services, service_categories


@require_GET
def service_search(request):
    query = request.GET.get("q", "").strip()[:120]
    category = request.GET.get("category", "").strip()
    if category not in {value for value, _ in service_categories()}:
        category = ""

    results = search_branch_services(query=query, category=category)
    paginator = Paginator(results, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "public/service_search.html",
        {
            "query": query,
            "selected_category": category,
            "categories": service_categories(),
            "page_obj": page_obj,
            "result_count": paginator.count,
        },
    )


@require_GET
def service_detail(request, public_id):
    service = get_object_or_404(
        active_branch_services(),
        public_id=public_id,
    )
    return render(
        request,
        "public/service_detail.html",
        {"service": service, "current_fee": service.current_fee},
    )


def get_featured_services(limit: int = 4):
    return list(active_branch_services().order_by("branch__name", "service__name_en")[:limit])
