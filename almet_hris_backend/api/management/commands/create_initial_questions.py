# api/management/commands/create_initial_questions.py
"""
Management command to create initial Exit Interview and Probation Review questions
Based on the Word document survey structure
"""

from django.core.management.base import BaseCommand
from django.apps import apps


class Command(BaseCommand):
    help = 'Create initial Exit Interview and Probation Review questions from Word document'

    def handle(self, *args, **kwargs):
        # Import models dynamically to avoid circular import issues
        ExitInterviewQuestion = apps.get_model('api', 'ExitInterviewQuestion')
        ProbationReviewQuestion = apps.get_model('api', 'ProbationReviewQuestion')
        
        self.stdout.write('Creating Exit Interview Questions...')
        self.create_exit_interview_questions(ExitInterviewQuestion)
        
        self.stdout.write('\nCreating Probation Review Questions...')
        self.create_probation_review_questions(ProbationReviewQuestion)
        
        self.stdout.write(self.style.SUCCESS('\n✅ All questions created successfully!'))

    def create_exit_interview_questions(self, ExitInterviewQuestion):
        """Create exit interview questions"""
        
        # Section 1: Role & Responsibilities
        questions = [
            {
                'section': 'ROLE',
                'question_text_en': 'How well did your job description reflect your actual duties?',
                'question_text_az': 'Vəzifə təsviriniz faktiki vəzifələrinizi nə dərəcədə əks etdirirdi?',
                'question_type': 'RATING',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'ROLE',
                'question_text_en': 'Were your responsibilities clearly defined?',
                'question_text_az': 'Məsuliyyətləriniz aydın müəyyən edilmişdimi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'ROLE',
                'question_text_en': 'What were the main challenges you faced in your role?',
                'question_text_az': 'Vəzifənizdə qarşılaşdığınız əsas çətinliklər nə idi?',
                'question_type': 'TEXTAREA',
                'order': 3,
                'is_required': False
            },
            
            # Section 2: Work Environment & Management
            {
                'section': 'MANAGEMENT',
                'question_text_en': 'How would you rate your relationship with your manager and colleagues?',
                'question_text_az': 'Menecer və həmkarlarınızla münasibətinizi necə qiymətləndirərdiniz?',
                'question_type': 'RATING',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'MANAGEMENT',
                'question_text_en': 'How effective was team collaboration?',
                'question_text_az': 'Komanda əməkdaşlığı nə qədər effektiv idi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'MANAGEMENT',
                'question_text_en': 'Did you receive adequate guidance and feedback?',
                'question_text_az': 'Kifayət qədər rəhbərlik və rəy aldınızmı?',
                'question_type': 'RATING',
                'order': 3,
                'is_required': True
            },
            {
                'section': 'MANAGEMENT',
                'question_text_en': 'Comments on leadership and management style',
                'question_text_az': 'Rəhbərlik və idarəetmə üslubu haqqında şərhlər',
                'question_type': 'TEXTAREA',
                'order': 4,
                'is_required': False
            },
            
            # Section 3: Compensation & Career Development
            {
                'section': 'COMPENSATION',
                'question_text_en': 'How satisfied were you with your salary and benefits?',
                'question_text_az': 'Maaş və müavinətlərdən nə dərəcədə razı idiniz?',
                'question_type': 'RATING',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'COMPENSATION',
                'question_text_en': 'Did you have opportunities for professional growth?',
                'question_text_az': 'Peşəkar inkişaf imkanlarınız var idimi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'COMPENSATION',
                'question_text_en': 'What could we have done to retain you?',
                'question_text_az': 'Sizi saxlamaq üçün nə edə bilərdik?',
                'question_type': 'TEXTAREA',
                'order': 3,
                'is_required': False
            },
            
            # Section 4: Work Conditions
            {
                'section': 'CONDITIONS',
                'question_text_en': 'How would you rate the working conditions?',
                'question_text_az': 'İş şəraitini necə qiymətləndirərdiniz?',
                'question_type': 'RATING',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'CONDITIONS',
                'question_text_en': 'How efficient were our systems and processes?',
                'question_text_az': 'Sistem və proseslərimiz nə qədər səmərəli idi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'CONDITIONS',
                'question_text_en': 'Suggestions for improvement',
                'question_text_az': 'Təkmilləşdirmə təklifləri',
                'question_type': 'TEXTAREA',
                'order': 3,
                'is_required': False
            },
            
            # Section 5: Company Culture & Values
            {
                'section': 'CULTURE',
                'question_text_en': 'Did you feel aligned with the company mission and values?',
                'question_text_az': 'Şirkətin missiya və dəyərləri ilə uyğunluq hiss edirdinizmi?',
                'question_type': 'RATING',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'CULTURE',
                'question_text_en': 'Was there a professional and respectful atmosphere?',
                'question_text_az': 'Peşəkar və hörmətli atmosfer var idimi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'CULTURE',
                'question_text_en': 'Describe our company culture in three words',
                'question_text_az': 'Şirkət mədəniyyətimizi üç sözlə təsvir edin',
                'question_type': 'TEXT',
                'order': 3,
                'is_required': False
            },
            
            # Section 6: Final Comments
            {
                'section': 'FINAL',
                'question_text_en': 'What is the main reason you are leaving?',
                'question_text_az': 'Ayrılmağınızın əsas səbəbi nədir?',
                'question_type': 'TEXTAREA',
                'order': 1,
                'is_required': True
            },
            {
                'section': 'FINAL',
                'question_text_en': 'Would you recommend this company to others?',
                'question_text_az': 'Bu şirkəti başqalarına tövsiyə edərdinizmi?',
                'question_type': 'RATING',
                'order': 2,
                'is_required': True
            },
            {
                'section': 'FINAL',
                'question_text_en': 'What would you change or improve about the company?',
                'question_text_az': 'Şirkət haqqında nəyi dəyişdirər və ya təkmilləşdirərdiniz?',
                'question_type': 'TEXTAREA',
                'order': 3,
                'is_required': False
            },
            {
                'section': 'FINAL',
                'question_text_en': 'Any other comments or feedback?',
                'question_text_az': 'Başqa şərhləriniz və ya rəyləriniz?',
                'question_type': 'TEXTAREA',
                'order': 4,
                'is_required': False
            },
        ]
        
        created_count = 0
        for q_data in questions:
            question, created = ExitInterviewQuestion.objects.get_or_create(
                section=q_data['section'],
                question_text_en=q_data['question_text_en'],
                defaults=q_data
            )
            if created:
                created_count += 1
                self.stdout.write(f"  ✓ Created: {q_data['question_text_en'][:60]}...")
        
        self.stdout.write(self.style.SUCCESS(f"  Total Exit Interview Questions Created: {created_count}"))

    def create_probation_review_questions(self, ProbationReviewQuestion):
        """Create probation review questions based on Word document"""
        
        # 30-Day Employee Questions
        employee_30_questions = [
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I understand my role and responsibilities',
                'question_text_az': 'Vəzifəm və əsas məsuliyyətlərim mənə aydındır',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I understand what is expected from me during my first 3 months',
                'question_text_az': 'İlk 3 ay ərzində məndən nə gözlənildiyini anlayıram',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'My onboarding experience was well-organized',
                'question_text_az': 'İşə adaptasiya prosesi yaxşı təşkil olunmuşdur',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'My manager provides clear guidance and support',
                'question_text_az': 'Menecer mənə aydın istiqamət və dəstək verir',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I feel welcomed by my team',
                'question_text_az': 'Komanda tərəfindən müsbət qarşılandığımı hiss edirəm',
                'question_type': 'YES_NO',
                'order': 5,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I have access to all tools and systems required for my job',
                'question_text_az': 'İşim üçün lazım olan bütün avadanlıqlar və sistemlər mövcuddur',
                'question_type': 'YES_NO',
                'order': 6,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'Policies and procedures were clearly explained to me',
                'question_text_az': 'Qaydalar və prosedurlar mənə aydın izah olunub',
                'question_type': 'YES_NO',
                'order': 7,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I feel positive about joining the company',
                'question_text_az': 'Bu şirkətə qoşulmaqla bağlı müsbət yanaşmam var',
                'question_type': 'YES_NO',
                'order': 8,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'I see how my role contributes to company goals',
                'question_text_az': 'Vəzifəmin şirkətin məqsədlərinə necə töhfə verdiyini anlayıram',
                'question_type': 'YES_NO',
                'order': 9,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'What has helped you most during your first month?',
                'question_text_az': 'İlk ay ərzində sizə ən çox nə kömək etdi?',
                'question_type': 'TEXTAREA',
                'order': 10,
                'is_required': False
            },
            {
                'review_type': 'EMPLOYEE_30',
                'question_text_en': 'What is unclear or could be improved?',
                'question_text_az': 'Nə aydın deyil və ya nəyi yaxşılaşdırmaq olar?',
                'question_type': 'TEXTAREA',
                'order': 11,
                'is_required': False
            },
        ]
        
        # 30-Day Manager Questions
        manager_30_questions = [
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'The employee understands their role and responsibilities',
                'question_text_az': 'İşçi öz vəzifəsini və məsuliyyətlərini anlayır',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'The employee completed mandatory onboarding trainings',
                'question_text_az': 'İşçi bütün məcburi onboarding təlimlərini tamamlayıb',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'The employee demonstrates engagement and willingness to learn',
                'question_text_az': 'İşçi motivasiyalıdır və öyrənməyə açıqdır',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'Tools, access, and systems are fully provided',
                'question_text_az': 'Lazımi avadanlıqlar və sistemlər tam təmin olunub',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'Any concerns at this stage?',
                'question_text_az': 'Bu mərhələdə hər hansı narahatlıq varmı?',
                'question_type': 'TEXTAREA',
                'order': 5,
                'is_required': False
            },
            {
                'review_type': 'MANAGER_30',
                'question_text_en': 'What support does the employee need?',
                'question_text_az': 'İşçinin hansı dəstəyə ehtiyacı var?',
                'question_type': 'TEXTAREA',
                'order': 6,
                'is_required': False
            },
        ]
        
        # 60-Day Employee Questions
        employee_60_questions = [
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I can perform my core responsibilities independently',
                'question_text_az': 'Əsas vəzifə öhdəliklərimi müstəqil şəkildə yerinə yetirə bilirəm',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I receive regular and constructive feedback',
                'question_text_az': 'Müntəzəm və konstruktiv rəy alıram',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'My goals and KPIs are clear',
                'question_text_az': 'Məqsədlərim və KPI-larım mənə aydındır',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I have received sufficient training for my role',
                'question_text_az': 'Vəzifəm üçün kifayət qədər təlim almışam',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'My manager supports my development',
                'question_text_az': 'Menecerim inkişafımı dəstəkləyir',
                'question_type': 'YES_NO',
                'order': 5,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I feel comfortable sharing concerns or ideas',
                'question_text_az': 'Fikirlərimi və narahatlıqlarımı rahat şəkildə bölüşə bilirəm',
                'question_type': 'YES_NO',
                'order': 6,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I feel motivated to give my best performance',
                'question_text_az': 'Ən yaxşı performansı göstərmək üçün motivasiyam var',
                'question_type': 'YES_NO',
                'order': 7,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'I feel committed to staying with the company',
                'question_text_az': 'Şirkətdə qalmaq niyyətindəyəm',
                'question_type': 'YES_NO',
                'order': 8,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'What support would help you perform better?',
                'question_text_az': 'Daha yaxşı performans göstərmək üçün hansı dəstəyə ehtiyacınız var?',
                'question_type': 'TEXTAREA',
                'order': 9,
                'is_required': False
            },
            {
                'review_type': 'EMPLOYEE_60',
                'question_text_en': 'Is there anything that may prevent you from succeeding here?',
                'question_text_az': 'Burada uğurlu olmağınıza mane ola biləcək hər hansı amil varmı?',
                'question_type': 'TEXTAREA',
                'order': 10,
                'is_required': False
            },
        ]
        
        # 60-Day Manager Questions
        manager_60_questions = [
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'The employee performs core tasks independently',
                'question_text_az': 'İşçi əsas tapşırıqları müstəqil yerinə yetirir',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'The employee meets expected performance standards',
                'question_text_az': 'İşçi gözlənilən performans səviyyəsinə uyğundur',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'The employee responds positively to feedback',
                'question_text_az': 'İşçi rəyə müsbət cavab verir',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'No engagement or behavioral risks observed',
                'question_text_az': 'Davranış və ya motivasiya riski müşahidə olunmur',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'Key strengths observed',
                'question_text_az': 'Müşahidə olunan əsas güclü tərəflər',
                'question_type': 'TEXTAREA',
                'order': 5,
                'is_required': False
            },
            {
                'review_type': 'MANAGER_60',
                'question_text_en': 'Development gaps or risks',
                'question_text_az': 'İnkişaf ehtiyacları və ya risklər',
                'question_type': 'TEXTAREA',
                'order': 6,
                'is_required': False
            },
        ]
        
        # 90-Day Employee Questions
        employee_90_questions = [
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I am confident in my ability to perform my role effectively',
                'question_text_az': 'Vəzifəmi effektiv şəkildə yerinə yetirə biləcəyimə əminəm',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'My role matches what was explained during recruitment',
                'question_text_az': 'Vəzifəm işə qəbul zamanı izah edilənlərlə uyğundur',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I understand my performance expectations clearly',
                'question_text_az': 'Performans gözləntilərini aydın şəkildə anlayıram',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I feel recognized for my contributions',
                'question_text_az': 'Gördüyüm işlərə görə tanındığımı hiss edirəm',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I see opportunities for growth within the company',
                'question_text_az': 'Şirkət daxilində inkişaf imkanları görürəm',
                'question_type': 'YES_NO',
                'order': 5,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I am satisfied with my onboarding experience',
                'question_text_az': 'İşə adaptasiya prosesindən məmnunam',
                'question_type': 'YES_NO',
                'order': 6,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'I would recommend this company as an employer',
                'question_text_az': 'Bu şirkəti işəgötürən kimi tövsiyə edərdim',
                'question_type': 'YES_NO',
                'order': 7,
                'is_required': True
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'What should we improve in the onboarding process?',
                'question_text_az': 'İşə adaptasiya prosesində nəyi yaxşılaşdırmaq olar?',
                'question_type': 'TEXTAREA',
                'order': 8,
                'is_required': False
            },
            {
                'review_type': 'EMPLOYEE_90',
                'question_text_en': 'What would increase your motivation to stay and grow here?',
                'question_text_az': 'Şirkətdə qalmaq və inkişaf etmək üçün motivasiyanızı nə artıra bilər?',
                'question_type': 'TEXTAREA',
                'order': 9,
                'is_required': False
            },
        ]
        
        # 90-Day Manager Questions
        manager_90_questions = [
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'The employee meets role requirements',
                'question_text_az': 'İşçi vəzifə tələblərinə cavab verir',
                'question_type': 'YES_NO',
                'order': 1,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'The employee aligns with company values and culture',
                'question_text_az': 'İşçi şirkət dəyərlərinə və mədəniyyətinə uyğundur',
                'question_type': 'YES_NO',
                'order': 2,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'The employee demonstrates long-term potential',
                'question_text_az': 'İşçi uzunmüddətli potensial nümayiş etdirir',
                'question_type': 'YES_NO',
                'order': 3,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'I recommend confirmation of employment',
                'question_text_az': 'Əməkdaşlığın təsdiqini tövsiyə edirəm',
                'question_type': 'YES_NO',
                'order': 4,
                'is_required': True
            },
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'Overall assessment and recommendations',
                'question_text_az': 'Ümumi qiymətləndirmə və tövsiyələr',
                'question_type': 'TEXTAREA',
                'order': 5,
                'is_required': False
            },
            {
                'review_type': 'MANAGER_90',
                'question_text_en': 'Development plan for next 6-12 months',
                'question_text_az': 'Növbəti 6-12 ay üçün inkişaf planı',
                'question_type': 'TEXTAREA',
                'order': 6,
                'is_required': False
            },
        ]
        
        # Combine all probation questions
        all_probation_questions = (
            employee_30_questions +
            manager_30_questions +
            employee_60_questions +
            manager_60_questions +
            employee_90_questions +
            manager_90_questions
        )
        
        created_count = 0
        for q_data in all_probation_questions:
            question, created = ProbationReviewQuestion.objects.get_or_create(
                review_type=q_data['review_type'],
                question_text_en=q_data['question_text_en'],
                defaults=q_data
            )
            if created:
                created_count += 1
                self.stdout.write(f"  ✓ Created: {q_data['review_type']} - {q_data['question_text_en'][:50]}...")
        
        self.stdout.write(self.style.SUCCESS(f"  Total Probation Review Questions Created: {created_count}"))