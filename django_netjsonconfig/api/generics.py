from django.core.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.response import Response

from ..tasks import subscribe
from ..utils import get_remote_template_data


class BaseTemplateDetailView(RetrieveAPIView):

    def get(self, request, *args, **kwargs):
        key = request.GET.get('key', None)
        opts = {
            'pk': kwargs['uuid'],
            'sharing': 'public'
        }
        if key:
            opts.update({
                'key': key,
                'sharing': 'secret_key'
            })
        template = get_object_or_404(self.template_model, **opts)
        # Setting the models for the serializers. This is done so
        # because this base view will be used by other repos who
        # will define their own concrete models for the serializers
        self.ca_serializer.Meta.model = self.ca_model
        self.cert_serializer.Meta.model = self.cert_model
        self.vpn_serializer.Meta.model = self.vpn_model
        self.template_detail_serializer.Meta.model = self.template_model
        serializer = self.template_detail_serializer(template)
        return Response(serializer.data)


class BaseListTemplateView(ListAPIView):
    """
    List all public templates and also enables
    search/filter of templates by template
    name or template description (des).
    """

    def get_queryset(self):
        name = self.request.GET.get('name', None)
        des = self.request.GET.get('des', None)
        qs = self.queryset.filter(sharing='public')
        if name and des is None:
            qs = qs.filter(name__icontains=name)
        elif des and name is None:
            qs = qs.filter(description__icontains=des)
        else:
            if name is not None and des is not None:
                qs = qs.filter(description__icontains=des,
                               name__icontains=name)
        return qs

    def get(self, request):
        data = self.get_queryset()
        self.list_serializer.Meta.model = self.template_model
        serializer = self.list_serializer(data, many=True)
        return Response(serializer.data)


class BaseCreateTemplateView(CreateAPIView):
    """
    API used to create external template.
    This API will be used at the template library
    backend repo
    """
    def save_template(self, template, import_url, request):
        template.full_clean()
        template.save()
        subscriber_url = '{0}://{1}'.format(request.META.get('wsgi.url_scheme'),
                                            request.get_host())
        subscribe.delay(template.id, import_url, subscriber_url, subscribe=True)

    def post(self, request, *args, **kwargs):
        import_url = request.POST.get('url', None)
        data = get_remote_template_data(import_url)
        errors = {}
        if data['type'] == 'vpn':
            ca = self.ca_model(**data['vpn']['ca'])
            try:
                ca.full_clean()
                ca.save()
            except ValidationError:
                ca = self.ca_model.objects.get(pk=ca.id)
            data['vpn']['cert']['ca'] = ca
            cert = self.cert_model(**data['vpn']['cert'])
            try:
                cert.full_clean()
                cert.save()
            except ValidationError:
                cert = self.cert_model.objects.get(pk=cert.id)
            data['vpn']['ca'] = ca
            data['vpn']['cert'] = cert
            vpn = self.vpn_model(**data['vpn'])
            try:
                vpn.full_clean()
                vpn.save()
            except ValidationError:
                vpn = self.vpn_model.objects.get(name=vpn.name)
            data['vpn'] = vpn
            template = self.template_model(**data)
            try:
                self.save_template(template, import_url, request)
            except ValidationError as e:
                errors.update({
                    'template_errors': e.messages
                })
                return Response(data=errors, status=500)
        else:
            template = self.template_model(**data)
            try:
                self.save_template(template, import_url, request)
            except ValidationError as e:
                errors.update({
                    'template_errors': e.messages
                })
                return Response(data=errors, status=500)
        return Response(status=200)


class BaseTemplateSubscriptionView(CreateAPIView):
    """
    Base view to handle template notification
    of templates
    """

    def post(self, request, *args, **kwargs):
        """
        create new notification record if this doesn't exist
        else update the is_subscribe field of the existing
        one accordingly
        """
        subscribe = request.POST.get('subscribe', False)
        template_pk = request.POST.get('template', None)
        template = self.template_model.objects.get(pk=template_pk)
        options = {
            'template': template,
            'subscriber': request.POST.get('subscriber', None)
        }
        try:
            # update TemplateSubscription for unsubscription
            # and re-subscription

            notification = self.template_subscribe_model.objects.get(**options)
            notification.subscribe = subscribe
            notification.save()
        except self.template_subscribe_model.DoesNotExist:
            # create a new record for new subscription
            options.update({
                'subscribe': subscribe
            })
            notify = self.template_subscribe_model(**options)
            notify.full_clean()
            notify.save()
        return Response(status=200)


class BaseTemplateSynchronizationView(CreateAPIView):
    """
    synchronize external templates and update last
    sync date
    """

    def post(self, request, *args, **kwargs):
        template_id = request.POST.get('template_id', None)
        subscriber_url = '{0}://{1}'.format(request.META.get('wsgi.url_scheme'),
                                            request.get_host())
        template = self.template_model.objects.get(pk=template_id)
        template.full_clean()
        template.save()
        subscribe.delay(template_id, template.url, subscriber_url,
                        subscribe=True)
        return Response(status=200)
