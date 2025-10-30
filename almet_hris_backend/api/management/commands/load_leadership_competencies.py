# api/management/commands/load_leadership_competencies.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.competency_models import (
    LeadershipCompetencyMainGroup,
    LeadershipCompetencyChildGroup,
    LeadershipCompetencyItem
)


class Command(BaseCommand):
    help = 'Load Leadership Competency Framework into database'

    def handle(self, *args, **kwargs):
        # Get or create admin user for created_by field
        admin_user = User.objects.filter(is_superuser=True).first()
        
        if not admin_user:
            self.stdout.write(self.style.WARNING('No admin user found. Creating items without creator.'))
        
        # THINK BIG Main Group
        think_big, _ = LeadershipCompetencyMainGroup.objects.get_or_create(
            name='THINK BIG',
            defaults={'created_by': admin_user}
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Found: {think_big.name}'))
        
        # Strategic Alignment Child Group
        strategic_alignment, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=think_big,
            name='STRATEGIC ALIGNMENT',
            defaults={'created_by': admin_user}
        )
        
        strategic_items = [
            "Demonstrates understanding of organization's opportunities in the market & continuously proposes and executes solutions to build on them",
            "Is aware and conscious of business risks and regularly proposes proactive solutions to avoid them",
            "Demonstrates understanding of organization's weaknesses & works to develops them with available resources",
            "Integrates and balances big-picture concerns with day-to-day activities not getting bogged into details and tactics",
        ]
        
        for item_text in strategic_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=strategic_alignment,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(strategic_items)} items to {strategic_alignment.name}'))
        
        # Analysis and Problem-Solving Child Group
        analysis_solving, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=think_big,
            name='ANALYSIS AND PROBLEM-SOLVING',
            defaults={'created_by': admin_user}
        )
        
        analysis_items = [
            "Breaks down problems into manageable components.",
            "Focuses on important information without getting bogged down in unnecessary detail.",
            "Seeks for solutions. Concentrates 20% of problem & 80% on solution",
            "IS data driven. Collects sufficient information to understand problems and issues.",
            "Applies accurate logic and data and makes sound decisions on everyday issues and problems.",
        ]
        
        for item_text in analysis_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=analysis_solving,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(analysis_items)} items to {analysis_solving.name}'))
        
        # Business and Financial Acumen Child Group
        business_acumen, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=think_big,
            name='BUSINESS AND FINANCIAL ACUMEN',
            defaults={'created_by': admin_user}
        )
        
        business_items = [
            "Demonstrates counсiousness about organization costs while taking decisions or bringing ideas",
            "Tracks and reports costs vs budget in own area",
            "Understands finacial metrics and cost drivers of business",
            "Draws accurate conclusions from financial and quantitative information.",
            "Accurately forecasts costs and revenues.",
        ]
        
        for item_text in business_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=business_acumen,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(business_items)} items to {business_acumen.name}'))
        
        # ==========================================
        # DRIVE RESULT Main Group
        # ==========================================
        drive_result, _ = LeadershipCompetencyMainGroup.objects.get_or_create(
            name='DRIVE RESULT',
            defaults={'created_by': admin_user}
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Found: {drive_result.name}'))
        
        # Manages Execution
        manages_execution, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_result,
            name='MANAGES EXECUTION',
            defaults={'created_by': admin_user}
        )
        
        execution_items = [
            "Establishes strategies for achieving individual or work unit goals.",
            "Sets objectives and KPIs for business units and drives people and processes towards achievement",
            "Acts resourcefully to ensure that work is completed within specified time and quality parameters.",
            "Identifies action steps needed to accomplish objectives.",
            "Establishes realistic plans and work schedules.",
            "Identifies resources (e.g., financial, headcount) needed to accomplish objectives, and seeks additional resources to complete tasks when needed.",
        ]
        
        for item_text in execution_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=manages_execution,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(execution_items)} items to {manages_execution.name}'))
        
        # Customer Focus
        customer_focus, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_result,
            name='CUSTOMER FOCUS',
            defaults={'created_by': admin_user}
        )
        
        customer_items = [
            "Spends sufficient time to learn more information about customers & suppliers and their specific and individual situation and needs",
            "Is well prepared before meeting and speaking to customers & suppliers",
            "Keeps customers in mind taking every day decisions",
            "Stives to push all organization to keep customers & suppliers in mind during daily activities",
            "Is ready to sacrifi own comfort for the sake of customers & suppliers satisfaction and attraction",
            "Follows up with customers & suppliers to ensure problems are solved",
        ]
        
        for item_text in customer_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=customer_focus,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(customer_items)} items to {customer_focus.name}'))
        
        # Leads for Performance
        leads_performance, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_result,
            name='LEADS FOR PERFORMANCE',
            defaults={'created_by': admin_user}
        )
        
        performance_items = [
            "Is highly responsansible in front of deadlines and objectives underatken",
            "Consistently achieves work objectives.",
            "Sets high standards of performance for self and others.",
            "Fosters a sense of urgency in others for achieving goals.",
        ]
        
        for item_text in performance_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=leads_performance,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(performance_items)} items to {leads_performance.name}'))
        
        # Drives Change and Innovation
        drives_change, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_result,
            name='DRIVES CHANGE AND INNOVATION',
            defaults={'created_by': admin_user}
        )
        
        change_items = [
            "Seeks and applies innovative and long term solutions to business",
            "Tactkles tough challenages or problems quickly and directly.",
            "Quickly identifies and supports useful changes.",
            "Serves as a change agent with own team",
        ]
        
        for item_text in change_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=drives_change,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(change_items)} items to {drives_change.name}'))
        
        # ==========================================
        # DRIVE PEOPLE Main Group
        # ==========================================
        drive_people, _ = LeadershipCompetencyMainGroup.objects.get_or_create(
            name='DRIVE PEOPLE',
            defaults={'created_by': admin_user}
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Found: {drive_people.name}'))
        
        # Communicates
        communicates, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_people,
            name='COMMUNICATES',
            defaults={'created_by': admin_user}
        )
        
        communication_items = [
            "Proactively shares information and viewpoints openly and directly with others.",
            "Conveys spoken and written information clearly and concisely.",
            "Speaks in a logical, organized manner.",
            "Involves the right people to obtain needed information.",
            "Listens carefully and attentively to others' opinions and ideas.",
            "Encourages others to share information and viewpoints frankly and openly.",
        ]
        
        for item_text in communication_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=communicates,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(communication_items)} items to {communicates.name}'))
        
        # Develops People
        develops_people, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_people,
            name='DEVELOPS PEOPLE',
            defaults={'created_by': admin_user}
        )
        
        development_items = [
            "Identifies the qualifications required for successful job performance.",
            "Makes accurate evaluations of people's capabilities and fit.",
            "Provides honest, helpful feedback to others on their performance.",
            "Provides useful real-time coaching to others.",
            "ecommends developmental activities to others.",
        ]
        
        for item_text in development_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=develops_people,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(development_items)} items to {develops_people.name}'))
        
        # Establishes Trust & Confidence
        trust_confidence, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=drive_people,
            name='ESTABLISHES TRUST & CONFIDENCE',
            defaults={'created_by': admin_user}
        )
        
        trust_items = [
            "Shows consistency between words and actions.",
            "Treats others fairly and consistently.",
            "Accepts responsibility for one's own performance and actions; does not cover up or blame others for problems or mistakes.",
            "Does not undermine others for own gain.",
            "Is honest and truthful in dealings with others.",
            "Acts consistently with stated policies and practices.",
            "Follows through on commitments.",
        ]
        
        for item_text in trust_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=trust_confidence,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(trust_items)} items to {trust_confidence.name}'))
        
        # ==========================================
        # BE A MODEL Main Group
        # ==========================================
        be_model, _ = LeadershipCompetencyMainGroup.objects.get_or_create(
            name='BE A MODEL',
            defaults={'created_by': admin_user}
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Found: {be_model.name}'))
        
        # Engages & Inspires
        engages_inspires, _ = LeadershipCompetencyChildGroup.objects.get_or_create(
            main_group=be_model,
            name='ENGAGES & INSPIRES',
            defaults={'created_by': admin_user}
        )
        
        inspire_items = [
            "Energizes others by clarifying the broader purpose and mission of their work.",
            "Encourages high standards of performance.",
            "Acknowledges others' efforts and accomplishments.",
            "Relates to people in an open, friendly, accepting, and respectful manner regardless of their organizational level, personality, or background.",
        ]
        
        for item_text in inspire_items:
            LeadershipCompetencyItem.objects.get_or_create(
                child_group=engages_inspires,
                name=item_text,
                defaults={'created_by': admin_user}
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(inspire_items)} items to {engages_inspires.name}'))
        
        # Summary
        total_main = LeadershipCompetencyMainGroup.objects.count()
        total_child = LeadershipCompetencyChildGroup.objects.count()
        total_items = LeadershipCompetencyItem.objects.count()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('LEADERSHIP COMPETENCY FRAMEWORK LOADED SUCCESSFULLY!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(self.style.SUCCESS(f'Total Main Groups: {total_main}'))
        self.stdout.write(self.style.SUCCESS(f'Total Child Groups: {total_child}'))
        self.stdout.write(self.style.SUCCESS(f'Total Competency Items: {total_items}'))
        self.stdout.write(self.style.SUCCESS('='*50 + '\n'))