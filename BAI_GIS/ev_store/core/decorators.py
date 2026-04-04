from django.shortcuts import render

def phan_quyen(roles=[]):
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            # Lấy vai trò của user hiện tại (Sửa 'request.user.vai_tro' thành trường chứa role thực tế của bạn)
            user_role = request.user.vai_tro 
            
            if user_role in roles:
                # Nếu quyền nằm trong danh sách cho phép -> Cho đi tiếp
                return view_func(request, *args, **kwargs)
            else:
                # Nếu không có quyền -> Trả về trang 404
                return render(request, '404.html', status=404)
                
        return wrapper_func
    return decorator