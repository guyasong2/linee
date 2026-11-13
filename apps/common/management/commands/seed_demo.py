from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import Branch, Organization
from apps.services.models import BranchService, Service, ServiceFee


def _service_data() -> list[dict]:
    return [
        {
            "code": "CONS",
            "name_en": "General consultation",
            "name_fr": "Consultation générale",
            "description_en": "A first point of contact with a clinician for common health concerns.",
            "description_fr": "Un premier point de contact avec un soignant pour les problèmes de santé courants.",
            "category": Service.Category.CONSULTATION,
            "fee": 5000,
            "duration": 15,
        },
        {
            "code": "CARD",
            "name_en": "Cardiology consultation",
            "name_fr": "Consultation de cardiologie",
            "description_en": "Assessment and follow-up for heart and blood-pressure concerns.",
            "description_fr": "Évaluation et suivi des problèmes cardiaques et de tension artérielle.",
            "category": Service.Category.CONSULTATION,
            "fee": 15000,
            "duration": 25,
        },
        {
            "code": "MATE",
            "name_en": "Antenatal care",
            "name_fr": "Consultation prénatale",
            "description_en": "Routine pregnancy follow-up with a midwife or clinician.",
            "description_fr": "Suivi routine de la grossesse avec une sage-femme ou un soignant.",
            "category": Service.Category.MATERNAL_HEALTH,
            "fee": 5000,
            "duration": 20,
        },
        {
            "code": "LAB",
            "name_en": "Laboratory tests",
            "name_fr": "Analyses de laboratoire",
            "description_en": "Sample collection for common laboratory tests.",
            "description_fr": "Prélèvement d'échantillons pour les analyses de laboratoire courantes.",
            "category": Service.Category.LABORATORY,
            "fee": 3000,
            "duration": 10,
        },
        {
            "code": "VACC",
            "name_en": "Vaccination",
            "name_fr": "Vaccination",
            "description_en": "Routine vaccination for children and adults.",
            "description_fr": "Vaccination de routine pour les enfants et les adultes.",
            "category": Service.Category.OTHER,
            "fee": 2000,
            "duration": 10,
        },
    ]


class Command(BaseCommand):
    help = "Create clearly labelled fictional demo organizations, branches and services."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        orgs = {
            "bonanjo": Organization.objects.update_or_create(
                slug="hopital-demo-bonanjo",
                defaults={
                    "name": "Hôpital Demo Bonanjo",
                    "legal_name": "Hôpital Demo Bonanjo (fictional demonstration facility)",
                    "status": Organization.Status.ACTIVE,
                    "default_language": Organization.Language.FRENCH,
                    "city": "Douala",
                    "address": "Bonanjo, Douala",
                },
            )[0],
            "akwa": Organization.objects.update_or_create(
                slug="centre-demo-akwa",
                defaults={
                    "name": "Centre de Santé Demo Akwa",
                    "legal_name": "Centre de Santé Demo Akwa (fictional demonstration facility)",
                    "status": Organization.Status.ACTIVE,
                    "default_language": Organization.Language.FRENCH,
                    "city": "Douala",
                    "address": "Akwa, Douala",
                },
            )[0],
        }

        branches = {
            "bonanjo_main": Branch.objects.update_or_create(
                organization=orgs["bonanjo"],
                code="BON",
                defaults={
                    "name": "Bonanjo Main",
                    "status": Branch.Status.ACTIVE,
                    "city": "Douala",
                    "address": "Rue Joss, Bonanjo, Douala",
                },
            )[0],
            "bonapriso": Branch.objects.update_or_create(
                organization=orgs["bonanjo"],
                code="BPR",
                defaults={
                    "name": "Bonapriso Annex",
                    "status": Branch.Status.ACTIVE,
                    "city": "Douala",
                    "address": "Bonapriso, Douala",
                },
            )[0],
            "akwa": Branch.objects.update_or_create(
                organization=orgs["akwa"],
                code="AKW",
                defaults={
                    "name": "Akwa Central",
                    "status": Branch.Status.ACTIVE,
                    "city": "Douala",
                    "address": "Akwa, Douala",
                },
            )[0],
        }

        service_data = {item["code"]: item for item in _service_data()}
        assignments = [
            ("bonanjo_main", ["CONS", "CARD", "MATE", "LAB"]),
            ("bonapriso", ["CONS", "LAB"]),
            ("akwa", ["CONS", "VACC", "LAB"]),
        ]

        created_services = 0
        created_offerings = 0
        created_fees = 0

        for branch_key, service_codes in assignments:
            branch = branches[branch_key]
            org = branch.organization
            for code in service_codes:
                data = service_data[code]
                service, service_created = Service.objects.update_or_create(
                    organization=org,
                    code=code,
                    defaults={
                        "name_en": data["name_en"],
                        "name_fr": data["name_fr"],
                        "description_en": data["description_en"],
                        "description_fr": data["description_fr"],
                        "category": data["category"],
                        "is_active": True,
                    },
                )
                created_services += int(service_created)

                offering, offering_created = BranchService.objects.update_or_create(
                    branch=branch,
                    service=service,
                    defaults={
                        "organization": org,
                        "default_duration_minutes": data["duration"],
                        "is_active": True,
                    },
                )
                created_offerings += int(offering_created)

                _, fee_created = ServiceFee.objects.update_or_create(
                    branch_service=offering,
                    effective_from=today,
                    defaults={
                        "organization": org,
                        "amount_xaf": data["fee"],
                        "currency": ServiceFee.Currency.XAF,
                        "is_active": True,
                        "published_at": now,
                    },
                )
                created_fees += int(fee_created)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready: "
                f"{Organization.objects.filter(slug__startswith='hopital-demo').count() + Organization.objects.filter(slug__startswith='centre-demo').count()} "
                f"organizations, {Branch.objects.filter(organization__in=orgs.values()).count()} branches, "
                f"{BranchService.objects.filter(organization__in=orgs.values()).count()} service offerings. "
                f"Created {created_services} services, {created_offerings} offerings, {created_fees} fees."
            )
        )
