
import typing as t

T = t.TypeVar('T')
T_co = t.TypeVar('T_co', covariant=True)
T_contra = t.TypeVar('T_contra', contravariant=True)

K = t.TypeVar('K')
K_co = t.TypeVar('K_co', covariant=True)
K_contra = t.TypeVar('K_contra', contravariant=True)

V = t.TypeVar('V')
V_co = t.TypeVar('V_co', covariant=True)
V_contra = t.TypeVar('V_contra', contravariant=True)

R = t.TypeVar('R')
R_co = t.TypeVar('R_co', covariant=True)
R_contra = t.TypeVar('R_contra', contravariant=True)

U = t.TypeVar('U')
U_co = t.TypeVar('U_co', covariant=True)
U_contra = t.TypeVar('U_contra', contravariant=True)

__all__ = [
  'T', 'T_co', 'T_contra',
  'K', 'K_co', 'K_contra',
  'V', 'V_co', 'V_contra',
  'R', 'R_co', 'R_contra',
  'U', 'U_co', 'U_contra',
]
