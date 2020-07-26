import csv, io
from django.conf import settings
from django.shortcuts import render, redirect, reverse, get_object_or_404
from .forms import PodcastForm
from .models import Podcast, Category
from reviews.models import Review
from django.contrib import messages
from .tasks import upload_pods
import requests




def pods(request):
    """ A view to return the Pods page """

    return render(request, 'pods/pods.html')


def upload_pod_data(request):
    """ A view to bulk upload podcast data via csv """
    template = "pods/upload_pods.html"
    data = Podcast.objects.all()
    prompt = {
        'order': 'Order of the CSV should be uuid, title, friendly_title, image_url, language, categories, website',
        'podcasts': data
    }
    # if GET return template
    if request.method == "GET":
        return render(request, template, prompt)
    # otherwise, capture uploaded file
    file_count = 0
    for file in request.FILES:
        # check if file is CSV, if not present error
        file_count += 1
        if not request.FILES[file].name.endswith('.csv'):
            messages.error(request, 'THIS IS NOT A CSV FILE')
    upload_pods(request)
    context = {}
    #messages.success(request, f'Upload complete! {upload} rows added to DB from {file_count} files.')
    messages.success(request, f'Files added to upload queue.')
    return render(request, template, context)


def upload_category_data(request):
    """ A view to bulk upload podcast category data via csv """
    template = "pods/upload_cats.html"
    data = Category.objects.all()
    prompt = {
        'order': 'Order of the CSV should be pk, name, friendly_name',
        'categories': data
    }
    # if GET return template
    if request.method == "GET":
        return render(request, template, prompt)
    # otherwise capture file upload
    csv_file = request.FILES['file']
    # validate is csv
    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'THIS IS NOT A CSV FILE')
    # read file
    data_set = csv_file.read().decode('UTF-8')
    io_string = io.StringIO(data_set)
    next(io_string)
    # upload to db
    for column in csv.reader(io_string, delimiter=',', quotechar="|"):
        _, create = Category.objects.update_or_create(
            pk=column[0],
            name=column[1].lower(),
            friendly_name=column[2],
        )
    context = {}
    return render(request, template, context)


def delete_all(request):
    """ A view to delete all pods from db """
    template = "pods/delete_all.html"
    # if GET return template
    if request.method == "GET":
        return render(request, 'pods/delete_all.html')
    else:
        if "duplicates" in request.POST:
            for pod in Podcast.objects.all().reverse():
                if Podcast.objects.filter(uuid=pod.uuid).count() > 1:
                    pod.delete()
        elif "pods" in request.POST:
            # check if there are pods to delete in db
            if int(Podcast.objects.all().count()) > 0:
                Podcast.objects.all().delete()
                messages.success(request, 'Deleted successfully')
                return render(request, template)
            else:
                messages.error(request, 'Nothing to delete')
                return render(request, template)
        elif 'fix_description' in request.POST:
            for pod in Podcast.objects.all():
                try:
                    if pod.description.count() < 10:
                        pod(description=f"The {pod.friendly_title} podcast.")
                        pod.save()
                    messages.success(request, 'descriptions fixed')
                    return render(request, template)
                except Exception as e:
                    messages.error(request, f'Unable to complete due to {e}')


def add_podcast(request):
    """
    A view to return the PodcastForm
    and allow user to add a single podcast to db
    """

    podcast_form = PodcastForm()
    template = 'pods/add_podcast.html'
    context = {
        "form": podcast_form,
    }
    if request.method == "POST":
        form = PodcastForm(request.POST, request.FILES)
        form.clean_friendly_title()
        if form.is_valid():
            form.clean_title()
            form.save()
            messages.success(request, "Successfully added podcast!")
            return redirect(reverse("add_podcast"))
        else:
            messages.error(request, "Failed to add podcast. Please ensure the form is valid.")
    else:
        return render(request, template, context)

def podcast_detail(request, id):
    """ A vew to show a specific podcast page. """
    from_page = request.META.get("HTTP_REFERER", "/")
    podcast = get_object_or_404(Podcast, pk=id)
    all_reviews = Review.objects.all()
    if all_reviews.filter(podcast_id=id).count() > 0:
        reviews = all_reviews.filter(podcast_id=id)
    else:
        reviews = None

    context = {
        "podcast": podcast,
        "reviews": reviews,
        "from_page": from_page,
    }

    return render(request, "pods/podcast_detail.html", context)

def import_from_itunes(request, id):
    itunes_lookup = requests.get(f'{settings.ITUNES_LOOKUP_URL}{id}')
    result = itunes_lookup.json()
    # this_id = result["results"][0]["collectionId"]
    # this_title = result["results"]["collectionName"].replace(" ", "_").lower()

    Podcast.objects.update_or_create(
        itunes_id=result["results"][0]["collectionId"],
        title=result["results"][0]["collectionName"].replace(" ", "_").lower(),
        friendly_title=result["results"][0]["collectionName"],
        image_url=result["results"][0]["artworkUrl600"],
        itunes_url=result["results"][0]["collectionViewUrl"],
    )
    category_lookup = Category.objects.get(friendly_name=result["results"][0]["primaryGenreName"]).id
    this_uuid = Podcast.objects.get(itunes_id=id).uuid
    print(f"UUID: {this_uuid}")
    pod = Podcast.objects.get(uuid=this_uuid)

    pod.category.set(str(category_lookup))


    context = {
        "id": this_uuid
    }
    return render(request, "pods/edit_podcast.html", context)

def edit_podcast(request, id):
    podcast = Podcast.objects.get(id=id)
    form = PodcastForm(instance=podcast)

    context = {
        "podcast": podcast,
        "form": form
    }

    if request.method == "GET":
        return render(request, "pods/edit_podcast.html", context)
    else:
        pass