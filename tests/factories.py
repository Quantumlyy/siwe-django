from django.contrib.auth import get_user_model


def named_user_factory(identity, request=None):
    UserModel = get_user_model()
    return UserModel.objects.create_user(
        username=f"custom_{identity.address[2:10].lower()}",
        first_name="SIWE",
    )
