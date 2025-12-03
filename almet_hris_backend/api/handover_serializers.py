# api/handover_serializers.py
from rest_framework import serializers
from .handover_models import (
    HandoverType, HandoverRequest, HandoverTask, 
    TaskActivity, HandoverImportantDate, HandoverActivity,
    HandoverAttachment
)
from .models import Employee
from django.contrib.auth.models import User


class HandoverTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverType
        fields = ['id', 'name', 'description', 'is_active', 'created_at']


class TaskActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    
    class Meta:
        model = TaskActivity
        fields = [
            'id', 'actor', 'actor_name', 'action', 
            'old_status', 'new_status', 'comment', 'timestamp'
        ]


class HandoverTaskSerializer(serializers.ModelSerializer):
    activity_log = TaskActivitySerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    
    class Meta:
        model = HandoverTask
        fields = [
            'id', 'handover', 'description', 'current_status', 
            'status_display', 'initial_comment', 'order', 
            'activity_log', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        # Get user from context
        user = self.context['request'].user
        
        # Create task
        task = HandoverTask.objects.create(**validated_data)
        
        # Log initial activity
        TaskActivity.objects.create(
            task=task,
            actor=user,
            action='Task Əlavə Edildi',
            old_status='-',
            new_status=task.current_status,
            comment=validated_data.get('initial_comment', '-')
        )
        
        return task


class HandoverImportantDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverImportantDate
        fields = ['id', 'handover', 'date', 'description', 'created_at']


class HandoverActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    
    class Meta:
        model = HandoverActivity
        fields = [
            'id', 'actor', 'actor_name', 'action', 
            'comment', 'status', 'timestamp'
        ]


class HandoverAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = HandoverAttachment
        fields = [
            'id', 'handover', 'file', 'file_url', 'original_filename',
            'file_size', 'file_size_display', 'file_type',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['file_size', 'file_type', 'uploaded_by', 'uploaded_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class HandoverRequestSerializer(serializers.ModelSerializer):
    # Employee details
    handing_over_employee_name = serializers.CharField(source='handing_over_employee.full_name', read_only=True)
    handing_over_position = serializers.CharField(source='handing_over_employee.job_title', read_only=True)
    handing_over_department = serializers.CharField(source='handing_over_employee.department.name', read_only=True)
    
    taking_over_employee_name = serializers.CharField(source='taking_over_employee.full_name', read_only=True)
    taking_over_position = serializers.CharField(source='taking_over_employee.job_title', read_only=True)
    
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    
    # Type
    handover_type_name = serializers.CharField(source='handover_type.name', read_only=True)
    
    # Status display
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Related data
    tasks = HandoverTaskSerializer(many=True, read_only=True)
    important_dates = HandoverImportantDateSerializer(many=True, read_only=True)
    activity_log = HandoverActivitySerializer(many=True, read_only=True)
    attachments = HandoverAttachmentSerializer(many=True, read_only=True)
    
    # Creator
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = HandoverRequest
        fields = [
            'id', 'request_id', 
            'handing_over_employee', 'handing_over_employee_name', 
            'handing_over_position', 'handing_over_department',
            'taking_over_employee', 'taking_over_employee_name', 'taking_over_position',
            'handover_type', 'handover_type_name',
            'start_date', 'end_date',
            'contacts', 'access_info', 'documents_info', 'open_issues', 'notes',
            'line_manager', 'line_manager_name',
            'status', 'status_display',
            'ho_signed', 'ho_signed_date',
            'to_signed', 'to_signed_date',
            'lm_approved', 'lm_approved_date', 'lm_comment', 'lm_clarification_comment',
            'rejected_at', 'rejection_reason',
            'taken_over', 'taken_over_date',
            'taken_back', 'taken_back_date',
            'tasks', 'important_dates', 'activity_log', 'attachments',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'request_id', 'status', 'ho_signed', 'ho_signed_date',
            'to_signed', 'to_signed_date', 'lm_approved', 'lm_approved_date',
            'rejected_at', 'taken_over', 'taken_over_date',
            'taken_back', 'taken_back_date', 'created_at', 'updated_at'
        ]


class HandoverRequestCreateSerializer(serializers.ModelSerializer):
    """Yeni handover yaratmaq üçün serializer"""
    tasks_data = serializers.ListField(child=serializers.DictField(), write_only=True)
    dates_data = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = HandoverRequest
        fields = [
            'handing_over_employee', 'taking_over_employee',
            'handover_type', 'start_date', 'end_date',
            'contacts', 'access_info', 'documents_info', 'open_issues', 'notes',
            'tasks_data', 'dates_data'
        ]
    
    def create(self, validated_data):
        tasks_data = validated_data.pop('tasks_data', [])
        dates_data = validated_data.pop('dates_data', [])
        
        # Get user from context
        user = self.context['request'].user
        validated_data['created_by'] = user
        
        # Create handover
        handover = HandoverRequest.objects.create(**validated_data)
        
        # Create tasks
        for idx, task_data in enumerate(tasks_data):
            task = HandoverTask.objects.create(
                handover=handover,
                description=task_data.get('description', ''),
                current_status=task_data.get('status', 'NOT_STARTED'),
                initial_comment=task_data.get('comment', ''),
                order=idx
            )
            
            # Log initial task activity
            TaskActivity.objects.create(
                task=task,
                actor=user,
                action='Initial Status Set',
                old_status='-',
                new_status=task.current_status,
                comment=task.initial_comment or '-'
            )
        
        # Create important dates
        for date_data in dates_data:
            HandoverImportantDate.objects.create(
                handover=handover,
                date=date_data.get('date'),
                description=date_data.get('description', '')
            )
        
        # Log creation activity
        HandoverActivity.objects.create(
            handover=handover,
            actor=user,
            action='Handover yaradıldı',
            comment='Yeni handover formu yaradıldı.',
            status=handover.status
        )
        
        return handover