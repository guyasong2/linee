from __future__ import annotations

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import AppointmentSlot
from apps.checklists.models import ChecklistItem, ChecklistVersion, DocumentChecklist
from apps.organizations.models import Branch, Counter, Organization
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
            "checklist": [
                {
                    "title_en": "Valid National ID Card (CNI) or Passport",
                    "title_fr": "Carte Nationale d'Identité (CNI) ou Passeport valide",
                    "description_en": "Original physical document required for patient identification.",
                    "description_fr": "Document original requis pour l'identification du patient.",
                    "is_mandatory": True,
                    "condition_en": "Must be valid and legible",
                    "condition_fr": "Doit être valide et lisible",
                },
                {
                    "title_en": "Previous Consultation Booklet / Carnet de Santé",
                    "title_fr": "Ancien carnet de santé ou dossier médical",
                    "description_en": "Helpful for the clinician to review past medical history.",
                    "description_fr": "Utile pour le clinicien pour examiner les antécédents médicaux.",
                    "is_mandatory": False,
                    "condition_en": "If available from prior visits",
                    "condition_fr": "Si disponible lors de visites précédentes",
                },
            ],
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
            "checklist": [
                {
                    "title_en": "National ID Card (CNI)",
                    "title_fr": "Carte Nationale d'Identité (CNI)",
                    "description_en": "Original valid identity document.",
                    "description_fr": "Document d'identité original valide.",
                    "is_mandatory": True,
                },
                {
                    "title_en": "Recent Electrocardiogram (ECG) or Lab Reports",
                    "title_fr": "Électrocardiogramme (ECG) récent ou bilans biologiques",
                    "description_en": "Bring test results from the last 30 days if existing.",
                    "description_fr": "Apportez les résultats des 30 derniers jours si existants.",
                    "is_mandatory": False,
                    "condition_en": "Recommended for follow-up patients",
                    "condition_fr": "Recommandé pour les patients en suivi",
                },
            ],
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
            "checklist": [
                {
                    "title_en": "National Identity Card",
                    "title_fr": "Carte d'Identité Nationale",
                    "description_en": "Patient identification.",
                    "description_fr": "Identification de la patiente.",
                    "is_mandatory": True,
                },
                {
                    "title_en": "Maternal Follow-Up Record (Carnet de Maternité)",
                    "title_fr": "Carnet de consultation prénatale",
                    "description_en": "Official pregnancy monitoring booklet.",
                    "description_fr": "Carnet officiel de suivi de grossesse.",
                    "is_mandatory": True,
                    "condition_en": "Mandatory for all routine follow-ups",
                    "condition_fr": "Obligatoire pour toutes les consultations de suivi",
                },
            ],
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
            "checklist": [
                {
                    "title_en": "Doctor's Lab Prescription (Ordonnance)",
                    "title_fr": "Prescription médicale d'analyses (Ordonnance)",
                    "description_en": "Signed medical order specifying exact lab tests required.",
                    "description_fr": "Prescription médicale signée indiquant les examens requis.",
                    "is_mandatory": True,
                },
                {
                    "title_en": "Fasting State (Jeûne)",
                    "title_fr": "État à jeun",
                    "description_en": "For glucose and lipid profile, do not eat 8-12 hours prior.",
                    "description_fr": "Pour glycémie et bilan lipidique, ne pas manger 8 à 12h avant.",
                    "is_mandatory": True,
                    "condition_en": "Required for blood sugar and cholesterol tests",
                    "condition_fr": "Requis pour glycémie et cholestérol",
                },
            ],
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
            "checklist": [
                {
                    "title_en": "Vaccination Card / Carnet de Vaccination",
                    "title_fr": "Carnet de vaccination",
                    "description_en": "To record dose batch number and date administered.",
                    "description_fr": "Pour enregistrer le numéro de lot et la date d'administration.",
                    "is_mandatory": True,
                },
            ],
        },
    ]


class Command(BaseCommand):
    help = "Create clearly labelled fictional demo organizations, branches, services, checklists, counters, and appointment slots."

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
                    "address": "Rue Joss, Bonanjo, Douala",
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

        # Seed physical Counters for branches
        counter_configs = [
            (
                "bonanjo_main",
                [("Counter 1", "C1"), ("Counter 2", "C2"), ("Consultation Desk A", "CDA")],
            ),
            ("bonapriso", [("Window 1", "W1"), ("Window 2", "W2")]),
            ("akwa", [("Desk 1", "D1"), ("Desk 2", "D2"), ("Vaccine Bay", "VB")]),
        ]
        total_counters = 0
        for branch_key, counters_list in counter_configs:
            branch = branches[branch_key]
            for c_name, c_code in counters_list:
                Counter.objects.update_or_create(
                    branch=branch,
                    code=c_code,
                    defaults={
                        "organization": branch.organization,
                        "name": c_name,
                        "status": Counter.Status.OPEN,
                    },
                )
                total_counters += 1

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

                # Seed Document Checklist for this service
                checklist, _ = DocumentChecklist.objects.update_or_create(
                    service=service,
                    defaults={
                        "organization": org,
                        "title_en": f"Requirements: {data['name_en']}",
                        "title_fr": f"Prérequis: {data['name_fr']}",
                        "is_active": True,
                    },
                )
                v1, _ = ChecklistVersion.objects.update_or_create(
                    checklist=checklist,
                    version_number=1,
                    defaults={"is_published": True, "published_at": now},
                )
                for order, item_data in enumerate(data.get("checklist", []), start=1):
                    ChecklistItem.objects.update_or_create(
                        version=v1,
                        order=order,
                        defaults={
                            "title_en": item_data["title_en"],
                            "title_fr": item_data.get("title_fr", ""),
                            "description_en": item_data.get("description_en", ""),
                            "description_fr": item_data.get("description_fr", ""),
                            "is_mandatory": item_data.get("is_mandatory", True),
                            "condition_note_en": item_data.get("condition_en", ""),
                            "condition_note_fr": item_data.get("condition_fr", ""),
                        },
                    )

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

                # Seed Appointment Slots for next 7 days
                for day_offset in range(1, 8):
                    target_date = today + datetime.timedelta(days=day_offset)
                    if target_date.weekday() != 6:  # Skip Sunday
                        for hour in (9, 10, 11, 14, 15):
                            start_time = datetime.time(hour, 0)
                            end_time = datetime.time(hour, data["duration"])
                            AppointmentSlot.objects.update_or_create(
                                branch_service=offering,
                                date=target_date,
                                start_time=start_time,
                                defaults={
                                    "end_time": end_time,
                                    "capacity": 3,
                                    "booked_count": 0,
                                    "is_active": True,
                                },
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(orgs)} organizations, {len(branches)} branches, "
                f"{total_counters} counters, {created_offerings} offerings, checklists and appointment slots seeded."
            )
        )
